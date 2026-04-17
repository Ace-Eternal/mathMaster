# Demo: Win11 local backend writing to remote Linux storage via SFTP

1. Copy `.env.example` to `.env`.
2. Set:
   - `STORAGE_BACKEND=sftp`
   - `STORAGE_BASE_DIR=/opt/mathmaster/data`
   - `SFTP_HOST=106.54.35.68`
   - `SFTP_PORT=22`
   - `SFTP_USERNAME=...`
   - `SFTP_PASSWORD=...`
3. Start backend locally on Win11.
4. Upload a PDF from the UI or `POST /api/papers/upload`.
5. Verify that the file is written under `/opt/mathmaster/data/raw/unpaired/paper/...` on the Linux server.
