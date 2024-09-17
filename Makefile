install:
	python3 -m pip install -r requirements.txt
upgrade:
	python3 -m pip install cambridge --upgrade
	python3 -m pip freeze > requirements.txt
uninstall:
	python3 -m pip uninstall -r requirements.txt -y
clean_cache:
	@rm -rf $HOME/.cache/cambridge
	@rm -rf $HOME/.cache/fakeua

gen:
	python3 -m pip freeze > requirements.txt

check:
	@echo "\n===> running Python linter - ruff"
	ruff check cambridge
	@echo "\n===> running static type checker - pyright"
	pyright cambridge
	@echo ""

env:
	python3 -m venv venv
clean_env:
	@rm -rf venv

release:
	flit publish
	@echo "\n===> waiting 3 seconds for PYPI being able to give the newest version"
	@sleep 3
	python3 -m pip install cambridge --upgrade
	python3 -m pip freeze > requirements.txt
	@grep cambridge requirements.txt || echo "Not found cambridge in requirements.txt"

.PHONY: clean
clean:
	@rm -rf cambridge/__pycache__
	@rm -rf cambridge/.DS_Store
	@rm -rf cambridge/.ruff_cache
	@rm -rf .DS_Store
	@rm -rf .ruff_cache/
	@rm -rf dist/
