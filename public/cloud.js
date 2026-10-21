/* Browser-owned queue: no dependency on instance affinity or server disk. */
const cloudJobs = [];
let cloudMode = false;
const runtimeReady = fetch('/api/health').then(response => response.json()).then(health => {
  cloudMode = health.mode === 'serverless';
  if (cloudMode) {
    document.querySelector('.local').textContent = '● SESSÃO NO NAVEGADOR';
    document.querySelector('#cloud-note').hidden = false;
  }
}).catch(() => {});

async function cloudFile(url, format, quality, progress) {
  const response = await fetch('/api/convert', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url,format,quality})});
  if (!response.ok) {
    const body = await response.json().catch(()=>({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'A conversão não pôde ser iniciada. Tente novamente.');
  }
  const reader = response.body.getReader(), decoder = new TextDecoder(), chunks = [];
  let buffer = '', filename = '', expected = 0, received = 0, done = false;
  try {
    while (true) {
      const packet = await reader.read();
      buffer += decoder.decode(packet.value || new Uint8Array(), {stream:!packet.done});
      let newline;
      while ((newline = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0,newline); buffer = buffer.slice(newline+1);
        if (!line.trim()) continue;
        const item = JSON.parse(line);
        if (item.type === 'error') throw new Error(item.message);
        if (item.type === 'progress') progress(item.value);
        if (item.type === 'file') {filename=item.name;expected=item.size;}
        if (item.type === 'chunk') {
          const binary=atob(item.data), bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));
          chunks.push(bytes); received += bytes.length;
        }
        if (item.type === 'done') done=true;
      }
      if (packet.done) break;
    }
  } catch (error) {await reader.cancel().catch(()=>{}); throw error;}
  if (!done || !filename || received !== expected) throw new Error('A conexão foi interrompida antes do fim do arquivo. Tente novamente.');
  return {name:filename, blob:new Blob(chunks,{type:format==='mp3'?'audio/mpeg':'video/mp4'})};
}

const crcTable = Array.from({length:256},(_,index)=>{for(let bit=0;bit<8;bit++)index=(index&1)?0xedb88320^(index>>>1):index>>>1;return index>>>0;});
async function zipFiles(files) {
  const chunks=[], central=[]; let offset=0, centralSize=0;
  for(const file of files){
    const name=new TextEncoder().encode(file.name), bytes=new Uint8Array(await file.blob.arrayBuffer());
    let crc=0xffffffff;for(const byte of bytes)crc=crcTable[(crc^byte)&255]^(crc>>>8);crc=(crc^0xffffffff)>>>0;
    const header=new Uint8Array(30+name.length), view=new DataView(header.buffer);
    view.setUint32(0,0x04034b50,true);view.setUint16(4,20,true);view.setUint16(6,0x800,true);view.setUint32(14,crc,true);view.setUint32(18,bytes.length,true);view.setUint32(22,bytes.length,true);view.setUint16(26,name.length,true);header.set(name,30);
    const entry=new Uint8Array(46+name.length), cv=new DataView(entry.buffer);
    cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0x800,true);cv.setUint32(16,crc,true);cv.setUint32(20,bytes.length,true);cv.setUint32(24,bytes.length,true);cv.setUint16(28,name.length,true);cv.setUint32(42,offset,true);entry.set(name,46);
    chunks.push(header,file.blob);central.push(entry);offset+=header.length+bytes.length;centralSize+=entry.length;
    await new Promise(resolve=>setTimeout(resolve,0));
  }
  const end=new Uint8Array(22), ev=new DataView(end.buffer);ev.setUint32(0,0x06054b50,true);ev.setUint16(8,files.length,true);ev.setUint16(10,files.length,true);ev.setUint32(12,centralSize,true);ev.setUint32(16,offset,true);
  return new Blob([...chunks,...central,end],{type:'application/zip'});
}

async function queueCloud(data, items) {
  const job={id:crypto.randomUUID(),title:data.title,format:data.format,status:'queued',progress:0,count:items.length};
  cloudJobs.push(job);
  (async()=>{
    const files=[];let total=0;
    job.status='processing';
    try{
      for(let index=0;index<items.length;index++){
        job.current=index+1;
        const file=await cloudFile('https://www.youtube.com/watch?v='+encodeURIComponent(items[index].id),data.format,data.quality,value=>job.progress=value);
        files.push(file);total+=file.blob.size;
        if(total>768*1024*1024)throw new Error('A seleção excede 768 MB no navegador. Divida a playlist em seleções menores.');
      }
      const output=files.length>1?{name:'Prometeus.zip',blob:await zipFiles(files)}:files[0];
      job.downloadUrl=URL.createObjectURL(output.blob);job.filename=output.name;job.status='completed';job.progress=100;
    }catch(error){job.status='error';job.error=error.message;}
    loadJobs();
  })();
  return job;
}
