## Set Up Your PyPI Token

Go to https://pypi.org → Account Settings → API tokens

Create a token with permission to upload to your package

Copy it, then go to your GitHub repo → Settings → Secrets and variables → Actions

Add a new secret:

```text
Name: PYPI_API_TOKEN
Value: <your-token-here>
```
