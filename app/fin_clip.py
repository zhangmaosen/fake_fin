import gradio as gr
from utils.functions import *
from utils.dbs import *


srt_file = gr.File()

srt_explorer = gr.FileExplorer(glob="*.srt", root_dir='./mp3', file_count='single')
srt_chunk_prompt = gr.Textbox(label="Clip SRT File Chunk Prompt")
srt_chunk_prompt_desc = gr.Textbox(label="Clip SRT File Chunk Prompt Description")
srt_chunk_prompt_templates = gr.Dropdown( label="Clip SRT File Chunk Prompt Templates")

srt_chunk_prompt_insert_btn = gr.Button("Insert")



srt_chunk_size = gr.Textbox(label="Clip SRT File Chunk Size")
srt_chunk_similarity = gr.Slider(minimum=0, maximum=1, step=0.1, label="Clip Similarity")
srt_content = gr.Textbox(label="SRT File Content")
srt_content_with_ts = gr.Textbox(label="SRT File Content with Timestamp", visible=False)
srt_text_output = gr.Textbox(label="SRT File Output line by line")
srt_chunk_button = gr.Button("Merge SRT File")

clip_sys_prompt = gr.Textbox(label="Clip System Prompt")
clip_usr_prompt = gr.Textbox(label="Clip User Prompt")

clip_button = gr.Button("Clip")
clip_output_text = gr.Textbox(label="Clip Output")

llm_model_selected = gr.Dropdown(["llama3.1:70b", "gemma2:9b-instruct-q4_0", "qwen2.5:72b-instruct","qwen2.5:32b-instruct","qwen2.5:7b-instruct"], label="Model", value="qwen2.5:32b-instruct")
llm_context_length = gr.Slider(minimum=0, maximum=30000, step=100, value=20000, label="LLM Context Length")
llm_temperature = gr.Slider(minimum=0, maximum=1, step=0.1, value=0, label="LLM Temperature")
llm_max_tokens = gr.Slider(minimum=0, maximum=10000, value=1024, step=1, label="LLM Max Tokens")

def init_chunk_prompt_templates(key, db_path):
    descs, prompts = query_prompt(key, db_path)
    return [gr.Dropdown(descs, interactive=True, type="index"), prompts]

    
with gr.Blocks() as demo:
    g_usr_prompt = gr.State('{}')
    g_db_path = gr.State('db/prompts.json')
    srt_chunk_prompt_tpl_list = gr.State([])
    srt_chunk_prompt_key = gr.State('srt_chunk_prompt')
    #g_usr_prompt.render()
    #g_db_path.render()
    srt_file.render()
    
    demo.load(init_chunk_prompt_templates, [srt_chunk_prompt_key, g_db_path], [srt_chunk_prompt_templates, srt_chunk_prompt_tpl_list])
    with gr.Row():
        llm_model_selected.render()
        llm_context_length.render()
        llm_temperature.render()
        llm_max_tokens.render()
# 把字幕转换为分段的文章
    
    with gr.Row():
        with gr.Column():
            srt_explorer.render() 
            srt_content.render()
            srt_content_with_ts.render()
        with gr.Column(scale=4):
            with gr.Row():
                with gr.Column(scale=2):
                    srt_chunk_prompt.render()
            
                with gr.Column():
                    srt_chunk_prompt_desc.render()
                    srt_chunk_prompt_templates.render()
                    srt_chunk_prompt_insert_btn.render()

                    

    srt_chunk_button.render()
    
    srt_chunk_prompt_templates.select(lambda x,y : y[x], [srt_chunk_prompt_templates, srt_chunk_prompt_tpl_list], srt_chunk_prompt)
    srt_chunk_prompt_insert_btn.click(insert_prompt, [srt_chunk_prompt, srt_chunk_prompt_desc, srt_chunk_prompt_key, g_db_path])
    srt_explorer.change(load_text_from_srt, srt_explorer, [srt_content, srt_content_with_ts])
    srt_chunk_button.click(run_model,[srt_chunk_prompt, srt_content, llm_model_selected, g_usr_prompt, llm_temperature, llm_context_length, llm_max_tokens], srt_text_output) #system_prompt, full_text, model_select, user_prompt, 
# 生成Clip
    with gr.Row():
        with gr.Column():
            
            srt_text_output.render()
        with gr.Column():
            clip_sys_prompt.render()
            clip_usr_prompt.render()
            clip_button.render()
    clip_output_text.render()

    
demo.launch(server_name='0.0.0.0', server_port=7777)