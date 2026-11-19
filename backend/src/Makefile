build-GroundingFunction:
	pip install -r requirements.txt \
		--platform manylinux2014_x86_64 \
		--implementation cp \
		--python-version 3.12 \
		--only-binary=:all: \
		--target "$(ARTIFACTS_DIR)"
	cp app.py "$(ARTIFACTS_DIR)"
