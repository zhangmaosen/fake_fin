import requests
transaction_input = {
"sender":"maosen",
"recipient":"maosen",
"amount":100
}
#transaction_input = json.dumps(transaction_input)

print(transaction_input)
# Send the transaction to the server
response = requests.post('http://127.0.0.1:5000/transactions/new', json=transaction_input)
print(response.content)