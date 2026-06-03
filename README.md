# GB Construction Lead Engine

Sito e dashboard per GB Construction:

- landing pubblica con hero immersivo, configuratore e acquisizione lead;
- dashboard staff con pipeline, preventivi, sopralluoghi e report;
- backend FastAPI con MongoDB, auth JWT, Meta Lead Ads webhook e AI Architect.

## Struttura

- `frontend/`: React CRA + Tailwind.
- `backend/`: FastAPI + MongoDB.
- `frontend/public/cantieri/`: asset pubblici realmente usati dal sito live.
- `PUBLIC/`: sorgenti media locali, ignorate da Git.
- `backend/storage/`: upload/output runtime AI Architect, ignorati da Git.

## Sviluppo

Backend:

```bash
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run start
```

Build frontend:

```bash
cd frontend
npm run build
```

## Deploy

Soluzione consigliata:

- frontend su Vercel;
- backend FastAPI su Railway;
- MongoDB su Railway o MongoDB Atlas;
- dominio del cliente, con `www` al frontend e `api` al backend.

Gli asset pubblici sono gia' dentro `frontend/public/cantieri`, quindi vengono copiati nel build React.
