import requests
from utils.util_methods import check_health_of_the_service, get_ports_of_nodes
import math
import random


# Checks the active nodes by checking with the service registry.
def check_active_nodes(coordinator):
    registered_nodes = []
    response = requests.get('http://127.0.0.1:8500/v1/agent/services')
    nodes = response.json()
    for each_service in nodes:
        service = nodes[each_service]['Service']
        registered_nodes.append(service)
    registered_nodes.remove(coordinator)
    health_status = []
    for each in registered_nodes:
        if check_health_of_the_service(each) == 'passing':
            health_status.append(each)
    print('Tha active nodes are: ', health_status)
    return health_status


def decide_roles(node_array):
    roles = {}
    num_nodes = len(node_array)

    # Randomly assign roles to nodes
    num_acceptors = min(2, num_nodes)
    num_learners = 1
    num_proposers = num_nodes - num_acceptors - num_learners
    roles = {'Acceptor': [], 'Learner': [], 'Proposer': []}
    for node in node_array:
        role = random.choice(['Acceptor', 'Learner', 'Proposer'])
        if role == 'Acceptor' and len(roles['Acceptor']) < num_acceptors:
            roles['Acceptor'].append(node)
        elif role == 'Learner' and len(roles['Learner']) < num_learners:
            roles['Learner'].append(node)
        else:
            roles['Proposer'].append(node)

    for node in roles['Acceptor']:
        roles[node] = 'Acceptor'
    for node in roles['Learner']:
        roles[node] = 'Learner'
    for node in roles['Proposer']:
        roles[node] = 'Proposer'

    print('roles', roles)
    return roles


# Inform each node about their role.
def inform_roles(roles, coordinator):
    ports_array = get_ports_of_nodes()
    del ports_array[coordinator]
    combined = {}
    for key in roles:
        if key in ports_array:
            combined[key] = (roles[key], ports_array[key])
    print('combined', combined)

    data_acceptor = {"role": "acceptor"}
    data_learner = {"role": "learner"}
    data_proposer = {"role": "proposer"}

    for each in combined:
        if combined[each][0] == 'Acceptor':
            url = 'http://localhost:%s/acceptor' % combined[each][1]
            print(url)
            requests.post(url, json=data_acceptor)
        elif combined[each][0] == 'Learner':
            url = 'http://localhost:%s/learner' % combined[each][1]
            print(url)
            requests.post(url, json=data_learner)
        else:
            url = 'http://localhost:%s/proposer' % combined[each][1]
            print(url)
            requests.post(url, json=data_proposer)
    return combined


# this method is used to schedule the range that they should start dividing based on the number.
def schedule_work_for_proposers(combined):
    count = 0
    range_array_proposers = []
    for each in combined:
        if combined[each][0] == 'Proposer':
            range_array_proposers.append(combined[each][1])
            count = count + 1

    random_number = read_number_from_file()
    proposer_list_len = len(range_array_proposers)
    number_range = math.floor(random_number / proposer_list_len)
    start = 2

    for each in range(proposer_list_len):
        divide_range = {
            "start": start,
            "end": start + number_range,
            "random_number": random_number
        }
        print(divide_range)
        url = 'http://localhost:%s/proposer-schedule' % range_array_proposers[each]
        requests.post(url, json=divide_range)
        start += number_range + 1


def read_number_from_file():
    file_name = "resources/PrimeNumbers.txt"
    with open(file_name, 'r') as f:
        lines = f.read().splitlines()
        random_number = int(random.choice(lines))
    print("Check {} is prime or not".format(random_number))
    return random_number


def get_node_ids(node_name):
    response = requests.get('http://127.0.0.1:8500/v1/agent/services')
    nodes = response.json()
    for each in nodes:
        if nodes[each]['Service'] == node_name:
            node_id = nodes[each]['ID']
    return node_id


# Update the Service Registry after deciding the roles.
def update_service_registry(roles):
    url = "http://localhost:8500/v1/agent/service/register"
    for each in roles:
        role_data = {
            "Name": each,
            "ID": get_node_ids(each),
            "Port": roles[each][1],
            "Meta": {"Role": roles[each][0]},
            "check": {
                "name": "Check Counter health %s" % roles[each][1],
                "tcp": "localhost:%s" % roles[each][1],
                "interval": "10s",
                "timeout": "1s"
            }
        }
        requests.put(url, json=role_data)
