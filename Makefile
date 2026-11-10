up:        ; docker compose up --build
down:      ; docker compose down
test:      ; cd backend && python -m pytest -q
lint:      ; cd backend && ruff check app tests
demo:      ; curl -F "name=demo" -F "file=@samples/exemple_specifications.docx" localhost:8000/api/v1/projects
