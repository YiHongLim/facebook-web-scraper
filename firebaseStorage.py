import firebase_admin
from firebase_admin import credentials, storage

# Initialize Firebase
cred = credentials.Certificate("evaluation-dataset-67b8dd770c30.json")
firebase_admin.initialize_app(cred, {"storageBucket": "gutter-bc42f.appspot.com"})

bucket = storage.bucket()
blobs = bucket.list_blobs(prefix='dataset/')  # Use your folder path

all_links = []
for blob in blobs:
    # Construct public URL
    file_name = blob.name.split('/')[-1]
    url = f"https://firebasestorage.googleapis.com/v0/b/gutter-bc42f.appspot.com/o/dataset%2F{file_name}?alt=media"
    all_links.append([file_name, url])  # add other matching metadata as needed
