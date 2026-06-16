# AI Architect Ground Truth Harness

Questo harness misura AI Architect su planimetrie reali anonimizzate prima del go-live pubblico.

## Uso

1. Crea una cartella `cases/case_XX/`.
2. Inserisci una planimetria anonimizzata come `plan.png`, `plan.jpg`, `plan.jpeg`, `plan.webp` o `plan.pdf`.
3. Compila `expected.json` seguendo lo schema nel case di esempio.
4. Esegui:

```powershell
cd backend
python ../scripts/ai_architect_ground_truth/run_ground_truth.py
```

Lo script scrive un report in `scripts/ai_architect_ground_truth/results/`.

## Verdetto

GO pubblico se:

- analisi accettabili >= 70%
- 2D non contraddittorie >= 50%
- errori gravi < 10%

Se una planimetria o un provider vision reale non sono disponibili, il case viene marcato come non valutabile. Lo script non usa fallback sintetici per assegnare un GO.

