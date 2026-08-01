.PHONY: run test
run:
	python -m recetamx.server

test:
	python -m unittest discover -s tests -v
