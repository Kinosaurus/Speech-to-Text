# KeenASR files go here

These files are proprietary (Keen Research) and are **not** committed to Git.
Copy them from your KeenASR Web SDK download so the folder looks like this:

```
public/vendor/keenasr/
├── keenasr-web.js
├── KeenASRCore.js
├── KeenASRCore.wasm
├── KeenASRCore.aw.js        <- audio worklet (note the dots)
├── KeenASRCore.ww.js        <- web worker    (note the dots)
└── models/
    └── keenAK3m-nnet3chain-en-us.tgz
```

Rules that matter:

- `keenasr-web.js` and every `KeenASRCore.*` file must stay in the **same
  folder**; the SDK loads them by relative path.
- Keep the file names exactly as shipped (`KeenASRCore.aw.js`, not
  `KeenASRCore_aw.js`).
- Do not unpack or re-zip the `.tgz` model bundle.
