## Development

### Getting Started

You need poetry:

```sh
curl -sSL https://install.python-poetry.org | python3 -
poetry config virtualenvs.in-project true
```

Then run

```sh
poetry install
source .venv/bin/activate
```

### Sanity Check

After making edits, run

```sh
./sanity.sh
```

which will run `lint` and `typecheck`.

### Unit Tests

```sh
poetry run task test
```
