# Static site (GitHub Pages)

These files power the **minimal PRO-800 export UI**.

- **GitHub Pages:** enable **Settings → Pages → Deploy from branch → `/docs` on `main`**.  
  Preview URL: `https://jeremybboy.github.io/gpu-audio-lab/` (layout + instructions only).

- **Full `.syx` download:** run the Flask app locally and open `http://127.0.0.1:5055/`  
  (see `experiments/04-audio-to-pro800-patch/README.md`).

`/.nojekyll` disables Jekyll so `app.js` is served as a static file.
