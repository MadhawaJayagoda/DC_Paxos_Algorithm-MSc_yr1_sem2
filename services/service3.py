import os
from flask import Flask, request, jsonify
from utils.util_methods import register_service, get_ports_of_nodes, generate_node_id, get_higher_nodes, election, \
    announce, ready_for_election, get_details, check_health_of_the_service
from utils.proposer_actions import get_acceptors_from_service_registry
from utils.coordinator_actions import check_active_nodes, decide_roles, inform_roles, schedule_work_for_proposers, \
    update_service_registry
from utils.check_prime import is_prime_number
from utils.acceptor_actions import get_learner_from_service_registry
from bully.Bully import Bully
import threading
import time
import random
import sys
import requests
from retry import retry
from multiprocessing import Value
import logging

counter = Value('i', 0)
app = Flask(__name__)

port_number = int(sys.argv[1])
assert port_number

node_name = sys.argv[2]
assert node_name

log_file = f"logs/{node_name}.log"
logging.basicConfig(filename=f"logs/{node_name}.log", level=logging.INFO)

# an array to capture the messages that receive from acceptors
learner_result_array = []

node_id = generate_node_id()
bully = Bully(node_name, node_id, port_number)

# Register service in the Service Registry
service_register_status = register_service(node_name, port_number, node_id)


def init(wait=True):
    if service_register_status == 200:
        ports_of_all_nodes = get_ports_of_nodes()
        del ports_of_all_nodes[node_name]

        # exchange details with each node
        node_details = get_details(ports_of_all_nodes)

        if wait:
            timeout = random.randint(5, 15)
            time.sleep(timeout)
            print('timeouting in %s seconds' % timeout)

        # checks if there is an election on going
        election_ready = ready_for_election(ports_of_all_nodes, bully.election, bully.coordinator)
        if election_ready or not wait:
            print('Starting election in: %s' % node_name)
            bully.election = True
            higher_nodes_array = get_higher_nodes(node_details, node_id)
            print('higher node array', higher_nodes_array)
            if len(higher_nodes_array) == 0:
                bully.coordinator = True
                bully.election = False
                announce(node_name)
                print('Coordinator is : %s' % node_name)
                print('****************End of election**********************')
                master_work()
            else:
                election(higher_nodes_array, node_id)
    else:
        print('Service registration is not successful')


# this api is used to exchange details with each node
@app.route('/nodeDetails', methods=['GET'])
def get_node_details():
    coordinator_bully = bully.coordinator
    node_id_bully = bully.node_id
    election_bully = bully.election
    node_name_bully = bully.node_name
    port_number_bully = bully.port
    return jsonify({'node_name': node_name_bully, 'node_id': node_id_bully, 'coordinator': coordinator_bully,
                    'election': election_bully, 'port': port_number_bully}), 200


# This API checks if the incoming node ID is grater than its own ID. If it is, it executes the init method and 
# sends an OK message to the sender. The execution is handed over to the current node. 


@app.route('/response', methods=['POST'])
def response_node():
    data = request.get_json()
    incoming_node_id = data['node_id']
    self_node_id = bully.node_id
    if self_node_id > incoming_node_id:
        threading.Thread(target=init, args=[False]).start()
        bully.election = False
    return jsonify({'Response': 'OK'}), 200


# This API is used to announce the coordinator details.
@app.route('/announce', methods=['POST'])
def announce_coordinator():
    data = request.get_json()
    coordinator = data['coordinator']
    bully.coordinator = coordinator
    print('Coordinator is %s ' % coordinator)
    return jsonify({'response': 'OK'}), 200


# When nodes are sending the election message to the higher nodes, all the requests comes to this proxy. As the init
# method needs to execute only once, it will forward exactly one request to the responseAPI. 


@app.route('/proxy', methods=['POST'])
def proxy():
    with counter.get_lock():
        counter.value += 1
        unique_count = counter.value
    url = 'http://localhost:%s/response' % port_number
    if unique_count == 1:
        data = request.get_json()
        requests.post(url, json=data)
    return jsonify({'Response': 'OK'}), 200


def master_work():
    active_nodes_array = set(check_active_nodes(node_name))
    roles = decide_roles(active_nodes_array)
    print("All the roles decided: ", roles)
    combined = inform_roles(roles, node_name)
    update_service_registry(combined)
    schedule_work_for_proposers(combined)
    print('roles', roles)
    proposer_count = 0
    for each in roles:
        if roles[each] == 'Proposer':
            proposer_count = proposer_count + 1
    print('proposer_count', proposer_count)
    proposer_count_data = {"proposer_count": proposer_count}

    for each in combined:
        if combined[each][0] == 'Learner':
            url = 'http://localhost:%s/learner' % combined[each][1]
            print(url)
            requests.post(url, json=proposer_count_data)


@app.route('/acceptor', methods=['POST'])
def acceptors():
    data = request.get_json()
    print(data)
    return jsonify({'response': 'OK'}), 200


@app.route('/learner', methods=['POST'])
def learners():
    data = request.get_json()
    print(data)
    return jsonify({'response': 'OK'}), 200


@app.route('/proposer', methods=['POST'])
def proposers():
    check_coordinator_health()
    data = request.get_json()
    print(data)
    return jsonify({'response': 'OK'}), 200


# This API receives the messages from proposers. If the message say the number is  prime, it will forward to the
# leaner without re-verifying. If it says the number is not prime, it will verify the number by its own and send
# the message to the learner. 


@app.route('/primeResult', methods=['POST'])
def prime_result():
    data = request.get_json()
    print('prime result from proposer', data['primeResult'])
    url = get_learner_from_service_registry()
    result = data['primeResult']
    result_string = {"result": result}
    print('Sending the result to learner: %s' % url)
    if 'is a prime number' in result:
        requests.post(url, json=result_string)
    else:
        print("Verifying the result as it says not a prime number.")
        number = int(result.split()[0])
        verified_result = is_prime_number(number, 2, number - 1)
        verified_result_string = {"result": verified_result}
        requests.post(url, json=verified_result_string)
    return jsonify({'response': 'OK'}), 200



# This API receives a number to be checked along with its range to be divided from the master node. Upon the sent 
# data, the calculation will be done and pass the result to a randomly selected acceptor. 


@app.route('/proposer-schedule', methods=['POST'])
def proposer_schedule():
    data = request.get_json()
    print(data)
    start = data['start']
    end = data['end']
    random_number = data['random_number']
    print('Checking %s number for prime....' % random_number)
    result_string = is_prime_number(random_number, start, end)
    data = {"primeResult": result_string}
    print(data)
    url_acceptor = get_acceptors_from_service_registry()
    print('Sending the result to a random acceptor %s' % url_acceptor)
    requests.post(url_acceptor, json=data)
    return jsonify({'response': 'OK'}), 200


# No node spends idle time, they always checks if the master node is alive in each 120 seconds.
def check_coordinator_health():
    threading.Timer(120.0, check_coordinator_health).start()
    health = check_health_of_the_service(bully.coordinator)
    if health == 'crashed':
        init()
    else:
        print('Coordinator is alive')


# This API receives the messages from acceptors and verify if there are any messages saying that number is not
# prime. If so it will decide that the number is not prime. Else it will decide the number is prime. 


@app.route('/finalResult', methods=['POST'])
def final_result():
    data = request.get_json()
    number = data['result'].split()[0]
    print('prime result from acceptor', data['result'])
    learner_result_array.append(data['result'])
    print(learner_result_array)

    count = 0
    for each_result in learner_result_array:
        if 'not a prime number' in each_result:
            count = count + 1
    if count > 0:
        final = '%s is not prime' % number
        print(final)
    else:
        final = '%s is prime' % number
        print(final)
    print('--------Final Result-----------')
    number_of_msgs = len(learner_result_array)
    print('Number of messages received from acceptors: %s' % number_of_msgs)
    print('Number of messages that says number is not prime: %s' % count)
    print(final)
    return jsonify({'response': final}), 200


timer_thread1 = threading.Timer(15, init)
timer_thread1.start()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=port_number)
