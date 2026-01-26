# share-clipboard Project
The Clipboard Sync Project is a innovative solution that enables seamless clipboard synchronization across multiple devices. This project consists of a client and server component, allowing users to share clipboard data in real-time. The client monitors the system clipboard, sends updates to the server, and receives clipboard data from the server to update the local clipboard. The server accepts connections from clients, monitors the system clipboard, and sends updates to connected clients. This project is ideal for users who need to share clipboard data across multiple devices, such as developers, designers, and researchers.

## 🚀 Features
- **Real-time Clipboard Synchronization**: Share clipboard data across multiple devices in real-time.
- **Multi-Device Support**: Connect multiple devices to the server and share clipboard data seamlessly.
- **Automatic Clipboard Monitoring**: The client and server continuously monitor the system clipboard for changes.
- **Bidirectional Communication**: Clients and server exchange clipboard data in JSON format.
- **Multi-Threading**: The client and server run in multiple threads to handle different tasks concurrently.

## 🛠️ Tech Stack
- **Socket Library**: For establishing network connections.
- **Threading Library**: For running multiple threads concurrently.
- **Pyperclip Library**: For accessing the system clipboard.
- **JSON Library**: For serializing and deserializing data.
- **Python**: As the primary programming language.

## 📦 Installation
### Prerequisites
- Python 3.8 or higher
- Pyperclip library
- Socket library
- Threading library
- JSON library

### Installation Steps
1. Clone the repository using `git clone https://github.com/DVHcoding/share-clipboard.git`.
2. Navigate to the project directory using `cd share-clipboard`.
3. Install the required libraries using `pip install -r requirements.txt`.
4. Run the server using `python server.py`.
5. Run the client using `python client.py`.

## 💻 Usage
1. Run the server on a device and note the IP address and port.
2. Run the client on another device and enter the server's IP address and port.
3. The client and server will establish a connection and start monitoring the system clipboard.
4. Any changes to the clipboard will be synchronized across all connected devices.

## 📂 Project Structure
```markdown
share-clipboard/
|-- client.py
|-- server.py
|-- requirements.txt
|-- README.md
```

## 📸 Screenshots

## 🤝 Contributing
Contributions are welcome! If you'd like to contribute to the project, please fork the repository and submit a pull request.

## 📝 License
This project is licensed under the MIT License.
