import pytest
from app.utils.dbs import insert_prompt

def test_insert_prompt():
    prompt = "test prompt"
    key = "test_key"
    db_path = "test_db.db"
    insert_prompt(prompt, key, db_path)
    # Add assertions to verify the expected behavior of the function