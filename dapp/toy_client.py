import gradio as gr
import requests
import json
def new_transaction(transaction_input):
    transaction_input = json.loads(transaction_input)
    # Send the transaction to the server
    response = requests.post('http://127.0.0.1:5000/transactions/new', json=transaction_input)
    print(response)
    return response.json()

with gr.Blocks() as demo:
    transaction_input = gr.Textbox(label="Transaction Input")
    gr.Examples(['''{
    "sender": "Alice",
    "recipient": "Bob",
    "amount": 5}
'''], inputs=transaction_input)
    submit_button = gr.Button("Submit")
    status_text = gr.Textbox(label="Status")

    submit_button.click(fn=new_transaction, inputs=transaction_input, outputs=status_text)

demo.launch()