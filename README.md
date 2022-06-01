# **FavShare: A Fault-Tolerent Distributed Key-Value Store**

This is fault-tolerent distributed key value store to update and share a list of favorites. This repo serves as a functioning implementaion of the [RAFT consensus protocol](https://raft.github.io/) for fault tolerence in a distributed environment. 

##  **Important note**
* There are two docker-compose files, each specific to Windows and Linux OS
    * The file - *docker-compose.dev.yml* is the docker-compose file specific to Windows OS
    * The file - *docker-compose-linux.yml* is the docker-compose specific to Linux
* Hence, when building the docker, use the OS specific commands given below:

##### Single Node
* Windows -  ```docker-compose -f docker-compose.dev.yml up --build```
* Linux - ```docker-compose -f docker-compose-linux.yml up --build``` 

##### Multi Node
* Windows -  ```docker-compose -f docker-compose.multi.yml up --build```
* Linux - ```docker-compose -f docker-compose-linux.multi.yml up --build``` 

## **Technology used**
* Docker is used to emulate a distributed environment.
* The app was developed using Python and the Flask micro web framework
* The DB connected is SQLite and we are using Flask-SQLAlchemy to query the DB
* The UI is developed using HTML and CSS

## **Operating Systems**
* Windows 10 and Fedora 34
