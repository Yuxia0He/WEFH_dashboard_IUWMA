# Internal deployment

The deployed dashboard is a read-only presentation of the generated `data.json` snapshot. The local Stella `.isdb` files and the Crocodile workbook are used by `refresh_data.py` when rebuilding the snapshot; they are not required by `app.py` at runtime.

## Recommended route: private Streamlit Community Cloud app

1. Create a private GitHub repository and copy this project into it.
2. Keep `app.py`, `data.json`, `content.json`, `evidence.json`, `requirements.txt`, `.streamlit/config.toml`, and `assets/` in the repository.
3. In Streamlit Community Cloud, create an app using `app.py` as the entrypoint.
4. Set the app to private and invite the stakeholder viewers.
5. When the model is rerun locally, run `python refresh_data.py`, commit the updated `data.json`, and push it to GitHub.

Do not commit the `.isdb` databases, source workbook, or local OneDrive paths to a public repository.

## Shared access-key mode

The app supports a single shared key for non-institutional circulation. Configure `CONNEXION_ACCESS_KEY` as a deployment secret or environment variable. Do not put the key in `app.py`, `content.json`, GitHub, or the URL. Users need only the dashboard link and the shared key; they do not need an institutional account.

This is appropriate for controlled circulation, not high-security data. Use HTTPS, rotate the key when the audience changes, and avoid placing confidential raw data in the deployed snapshot.

## Container deployment

Build and run locally:

```powershell
docker build -t connexion-dashboard .
docker run --rm -p 8501:8501 connexion-dashboard
```

The same image can be deployed to Azure App Service, Azure Container Apps, or an institutional container platform. Put authentication in front of the app through the hosting platform, such as Microsoft Entra ID; do not implement credentials in `app.py`.

## Refresh workflow

The deployed app is a snapshot. To publish new model outputs:

```powershell
python refresh_data.py
git add data.json
git commit -m "Update model output snapshot"
git push
```

The host then redeploys or refreshes the app from the updated repository.
