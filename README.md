# Paxos Algorithm Implementation- MSc Year 1 Semester 2

This GitHub repository contains an implementation of the Paxos algorithm, providing a robust and efficient solution for reaching consensus in distributed systems. This is done as an assignment for MSc Year 1 Semester 2 - Distributed Computing, where there is a list of numbers and out of them prime numbers should be detected using Paxos algorithm. 
There are mainly three roles:
1. Proposers: Proposers are responsible for initiating the consensus process by proposing a value to be agreed upon. In this, they are the once who does the calculation and send the message that a number is prime or not. They send proposal messages to the acceptors.
2. Acceptors: Acceptors are the entities that receive proposals from proposers. They maintain a log of accepted proposals and respond to the proposers' messages. Acceptors can either accept or reject a proposal based on certain conditions.
3. Learners: Learners are the entities that observe the messages exchanged between the proposers and acceptors. They keep track of the accepted proposals and learn the agreed-upon value. Finally, it says that the number is prime or not. 

Also, there is a master node whose primary purpose is to manage and coordinate the activities of other nodes. It does work such as:
* Resource allocation: The master node is responsible for allocating and managing system resources among the nodes.
* Task scheduling: The master node decides which tasks or jobs should be executed by which worker nodes and in what order. It takes into account factors like node availability, load balancing, and optimizing resource utilization to schedule tasks efficiently. 

As distributed systems continue to evolve, Paxos remains a key algorithmic framework that ensures the reliable coordination and agreement among processes. It is a valuable tool in maintaining system integrity and consistency. Paxos contributes to the advancement of distributed computing, enabling the development of complex and scalable applications that can effectively operate in distributed and decentralized environments.
