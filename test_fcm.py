import firebase_admin
from firebase_admin import credentials, messaging

# Initialize the Firebase Admin SDK with the downloaded JSON key
cred = credentials.Certificate('/home/abrar/Downloads/secondary-sales-6ec10-firebase-adminsdk-fbsvc-ebcdd063af.json')
firebase_admin.initialize_app(cred)

# The token we extracted from your phone's screen
device_token = "dwilH4AzRlGqnEz28-ksk5:APA91bEB6l5ud4sMj025g5gBwaSjC6YcydJcw38DJNO6gvZm_nLR8ohLC-75ZRns_U6GLZf6sNXa_BFGPHLJfXg8Iw535WT5BrtKhhOQNoUTXClXeuFvJvA"

# Construct the test message
message = messaging.Message(
    notification=messaging.Notification(
        title='Hello from Python!',
        body='This is a test notification from your backend script.',
    ),
    token=device_token,
)

# Send the message
try:
    response = messaging.send(message)
    print(f"Successfully sent message! Response: {response}")
except Exception as e:
    print(f"Error sending message: {e}")
