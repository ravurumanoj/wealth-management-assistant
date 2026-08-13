from security import create_access_token

client_id = str(input("Please enter your Client ID: ")).strip()
client_secret = str(input("Please enter your Client Secret: ")).strip()

token = create_access_token(username=client_id, secret=client_secret)

print(token)