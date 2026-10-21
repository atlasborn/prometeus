# Prometeus

Web app de conversão de vídeos e playlists públicas do YouTube, com tema gamer escuro e vermelho. Interface em português, responsiva e sem conteúdo de demonstração.

- MP3 em 128, 192 ou 320 kbps.
- MP4 em até 360p, 720p ou 1080p, conforme a fonte disponível.
- Seleção individual ou de todos os itens de uma playlist.
- Fila com dois processos simultâneos e progresso do arquivo atual.
- Downloads individuais ou ZIP para múltiplos itens.

## Executar com Docker

```sh
docker compose up --build -d
```

Abra http://localhost:7189. A imagem instala Python, yt-dlp, Node e FFmpeg. O volume `downloads` mantém os arquivos. A porta é publicada apenas no dispositivo local.

## Executar com Python

Requer Python 3.10+, FFmpeg e Node 20+ no PATH.

```sh
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

Linux/macOS:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

## Verificação

```sh
python -m unittest discover -s tests -v
node --check public/app.js
```

## Operação

O backend usa subprocessos reais do yt-dlp e FFmpeg. Nenhuma API de conversão externa, chave, conta ou banco de dados é necessária. O YouTube pode bloquear requisições por IP ou exigir autenticação; esses erros aparecem na interface. Atualize o yt-dlp regularmente, conforme sua [documentação oficial](https://github.com/yt-dlp/yt-dlp#installation).

As conversões ficam na memória da sessão do servidor. Reiniciá-lo limpa a lista, mas mantém os arquivos no disco; remova downloads antigos periodicamente. A análise aceita até 500 itens por playlist e a fila comporta até 10 pedidos ativos. O limite por arquivo de origem é 2 GB. Não há autenticação: a execução padrão é local. Para exposição pública, adicione autenticação, armazenamento por usuário, limites de uso e expiração dos arquivos antes de publicar.

A versão local usa o servidor persistente descrito acima. A configuração `vercel.json` publica a interface e o adaptador FastAPI de `api/index.py`, que converte um vídeo por requisição e transmite o arquivo ao navegador. A fila e os arquivos online pertencem à sessão do navegador: mantenha a aba aberta. O ZIP é montado no cliente; nenhum download depende da memória ou do disco de outra instância Vercel. Limites online: 45 segundos de processamento por vídeo (função de até 60 segundos no plano atual), 200 MB por fonte, 256 MB por arquivo final e 768 MB por seleção. Use seleções menores ou a versão local para arquivos maiores. `HOST` e `PORT` configuram a interface de rede e a porta; no Docker o host é `0.0.0.0`.

Converta apenas conteúdo próprio ou autorizado. Os arquivos `webapp.py` e `vercel.json`, caso presentes no repositório, pertencem à implementação anterior; o novo ponto de entrada é `server.py`.
