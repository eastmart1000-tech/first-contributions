# Quick Autofill

A small Chrome extension. You save your details once, and then one click fills in the matching fields on whatever form you're looking at: job applications, school forms, sign-up pages.

- It only **fills in** fields. It never clicks buttons or submits anything, so you always check the form and submit it yourself.
- It skips passwords, card numbers, CVVs, SSNs and similar sensitive fields.
- Your details are stored only in your browser (`chrome.storage.local`). Nothing is sent anywhere.
- Filled fields get a short orange outline so you can see what changed.

## Install

1. Download this folder. On GitHub: **Code → Download ZIP**, then unzip it.
2. Open `chrome://extensions` in Chrome (Edge: `edge://extensions`).
3. Turn on **Developer mode** (top-right toggle).
4. Click **Load unpacked** and pick the `autofill-extension` folder.
5. Pin it from the puzzle-piece menu so the icon stays in your toolbar.

## Use

1. Click the icon, open **My details**, and fill them in. They save as you type.
2. Go to a form, click the icon, and press **Fill this page**.
3. Check the filled fields, then submit the form yourself.

By default it leaves alone any field that already has text. Tick **Replace fields that already have text** to overwrite them.

## Limits

- It guesses which field is which from the field's label, name and placeholder. Unusual forms may need a few fields typed by hand.
- It doesn't reach forms inside embedded frames, or pages Chrome protects (`chrome://` pages, the Chrome Web Store).

## Files

| File | What it does |
| --- | --- |
| `manifest.json` | Extension settings and permissions (`activeTab`, `scripting`, `storage`) |
| `popup.html` / `popup.css` / `popup.js` | The popup where you enter your details and press Fill |
| `fill.js` | The code that runs on the page, matches fields and fills them |
