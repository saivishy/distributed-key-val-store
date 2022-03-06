# **FavShare - Flask Application Readme**

## **Technology used**
* The app was developed using Python and the Flask micro web framework
* The DB connected is SQLite and we are using Flask-SQLAlchemy to query the DB
* The UI is developed using HTML and CSS

## **Operating Systems**
* Windows 10 and Fedora

##  **Important note**
* There are two docker-compose files, each specific to Windows and Linux OS
    * The file - *docker-compose.dev.yml* is the docker-compose file specific to Windows OS
    * The file - *docker-compose-linux.yml* is the docker-compose specific to Linux
* Hence, when building the docker, use the OS specific commands given below:
<<<<<<< HEAD
    * Windows -  ```docker-compose -f docker-compose.dev.yml up --build```
    * Linux - ```docker-compose -f docker-compose-linux.yml ip --build``` 
* When running multiple containers use the following docker compose:
    * Windows -  ```docker-compose -f docker-compose.multi.yml up --build``` 
=======
>>>>>>> 89bd0c88d8f9fe17177f5ee88810c29963e4b29a

##### Single Node
* Windows -  ```docker-compose -f docker-compose.dev.yml up --build```
* Linux - ```docker-compose -f docker-compose-linux.yml ip --build``` 

##### Multi Node
* Windows -  ```docker-compose -f docker-compose.multi.yml up --build```
* Linux - ```docker-compose -f docker-compose-linux.multi.yml ip --build``` 

<!-- 
## **Application Video**
* [Box Link](https://buffalo.box.com/s/p5x0sm07q9uy6b3xo7mvijivsdwiovtf)
 -->
