from tinydb import TinyDB, Query

# function: insert prompt into tinydb
def insert_prompt(prompt, prompt_desc, key, db_path):
    if prompt == '':
        return
    db = TinyDB(db_path)
    db.insert({'key': key, 'desc': prompt_desc, 'prompt': prompt})

def query_prompt(key, db_path):
    db = TinyDB(db_path)
    query = Query()
    result = db.search(query.key == key)
    # 获得数组中每个dict的key为desc的所有值
    descs = [d['desc'] for d in result if 'desc' in d]
    prompts = [d['prompt'] for d in result if 'prompt' in d]
    print(descs)
    return [descs, prompts]
