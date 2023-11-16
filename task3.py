import gurobipy as gp, csv
from gurobipy import GRB

model = gp.Model("task3")

#simplifying loading of files such that a csv can be loaded into a nested list
#for example the line "4801,20,9,2" would be [4801,20,9,2], and this would be done for each line
def csv_loader(filename):
    l = []
    with open(f"{filename}.csv") as f:
        read = csv.reader(f)
        next(read)
        for line in f:
            l.append(line.strip().split(','))
        return l
        

#set of suppliers, such that suppliers[ID] = total supply
suppliers = {int(sup[0]) : float(sup[1]) for sup in csv_loader("suppliers")}

#Create an additional supplier with a unique ID, so that it can be treated as any other supplier
third_party_supplier = max([i for i in suppliers])+1
suppliers[third_party_supplier] = GRB.INFINITY #this supplier has no supply limit

#set of hubs
hubs = [int(hub[0]) for hub in csv_loader("hubs")] #reminder that capacity is constant

#set of plants
plants = [int(plant[0]) for plant in csv_loader("plants")] #reminder that capacity is constant

#cost of travel in arcs for the full distance, such that truck_cost[(i,j)] = cost between i,j per Mg
truck_cost = {(int(e[0]), int(e[1])) : float(e[2]) * float(e[3]) for e in csv_loader("roads_s_h")}
train_cost = {(int(e[0]), int(e[1])) : float(e[2]) * float(e[3]) for e in csv_loader("railroads_h_p")}

#Create a constant cost of travel per Mg between the third party suppliers to each hub
for j in hubs:
    truck_cost[third_party_supplier, j] = 2000


#note that
TRUCK_CAPACITY = 500
TRAIN_CAPACITY = 20000

#and that for the trains
HUB_COST = 3476219
HUB_CAPACITY = 300000

#note that
PLANT_YIELD = 232 #liters, per Mg
PLANT_COST = 130956797

#biomass conversion, to keep everything in the same unit
biomass_to_ethanol = lambda N : N*PLANT_YIELD
ethanol_to_biomass = lambda N : N/PLANT_YIELD

#more useful constants
PLANT_CAPACITY = ethanol_to_biomass(152063705)   #152063705 liters -> 655,447 Mg
PRODUCTION_GOAL = ethanol_to_biomass(800000000)  #500,000,000 liters -> 2,155,172 Mg
#i.e. if we know that the plants have been supplied at least 2,155,172 Mg, we know it can produce 500M liters
#3,448,275



"""
Decision variables
"""
#Create decision variables for flow between suppliers and hubs 
truck_flow = {}
for s in suppliers:
    
    #I deal with this in a seperate loop to avoid if-statement bombing
    if s == third_party_supplier:
        truck_flow[s] = {}
        continue
    
    truck_flow[s] = {}
    for h in hubs:
        truck_flow[s][h] = []
        
        #The maximim supplied betwen i,j would normally be emptying the supply. This is because that is the
        #first limit we reach. Effectively: min(max(source), max(destination). I calculate it only for modularity.
        max_trips = int(min(suppliers[s], HUB_CAPACITY) / TRUCK_CAPACITY)+1
        for m in range(max_trips+1):
            #Limiting the possible variables of each individual trips, up to max_trips, to be 0 <= x <= 500
            #This adds the constraint of the truck's capacity
            var = model.addVar(vtype=GRB.CONTINUOUS, lb=0.00, ub=TRUCK_CAPACITY, name=f'{s}->{h} ({m})')
            truck_flow[s][h].append(var)


#I personally did not add the truck's cap constraint to the transportation between third party supply,
#I just assumed that this would not be my problem. And that the cost of 2000 "includes delivery"
for h in hubs:
    truck_flow[third_party_supplier][h] = []
    var = model.addVar(vtype=GRB.CONTINUOUS, lb=0.00, ub=HUB_CAPACITY, name=f'{s}->{h} ({m})')
    truck_flow[s][h].append(var)
        

#Similar strategy as before, just with different sources and destiantions
train_flow = {}
for h in hubs:
    train_flow[h] = {}
    for p in plants:
        train_flow[h][p] = []
        
        #Again, I calculate it only for modularity.
        max_trips = int(min(HUB_CAPACITY, PLANT_CAPACITY) / TRAIN_CAPACITY)+1
        for m in range(max_trips+1):
            #Again, imposing the train capacity constraint for each variable
            var = model.addVar(vtype=GRB.CONTINUOUS, lb=0.00, ub=TRAIN_CAPACITY, name=f'{h}->{p} ({m})')
            train_flow[h][p].append(var)


#Create decision variables for the plant selection
plant_select = model.addVars(plants, vtype=GRB.BINARY, name="plant_selection")
hub_select = model.addVars(hubs, vtype=GRB.BINARY, name="hub_selection")

"""
"""



"""
Objective function:
"""
#Same as before, just changing destination to hubs instead of plants
truck_transport = gp.quicksum(
    (truck_flow[i][j][f]*truck_cost[i,j]) for i in suppliers for j in hubs for f in range(len(truck_flow[i][j]))
    )

truck_loading_cost = gp.quicksum(
    10000 for i in suppliers for j in hubs for f in range(len(truck_flow[i][j])) if truck_flow[i][j][f]
)

#Quite similar, using different metrics for costs
train_transport= gp.quicksum(
    (train_flow[i][j][f]*train_cost[i,j]) for i in hubs for j in plants for f in range(len(train_flow[i][j]))
)

train_loading_cost = gp.quicksum(
    60000 for i in hubs for j in plants for f in range(len(train_flow[i][j])) if train_flow[i][j][f]
)

#Same as before
plant_investment = gp.quicksum(plant_select[p] * PLANT_COST for p in plants)
hub_investment = gp.quicksum(hub_select[h] * HUB_COST for h in hubs)

model.setObjective(  truck_transport + train_transport
                   + truck_loading_cost + train_loading_cost
                   + plant_investment + hub_investment,
                   GRB.MINIMIZE)

"""
"""




"""
Constraints:
"""
#Constraint: Total amount delivered to plants equals production goal
sum_at_plants = gp.quicksum(train_flow[i][j][f] for i in hubs for j in plants for f in range(len(train_flow[i][j])))
model.addConstr(sum_at_plants >= PRODUCTION_GOAL)

#Constraint: Total amount sent from suppliers must be less than or equal to the available supply
for i in suppliers:
    supplier_sum = gp.quicksum(truck_flow[i][j][f] for j in hubs for f in range(len(truck_flow[i][j])))
    model.addConstr(supplier_sum <= suppliers[i])

#Constraint: The amount delivered to each hub must be less than or equal to the hub's capacity
hub_in = {} #see constraint below
for j in hubs:
    hub_in[j] = gp.quicksum(truck_flow[i][j][f] for i in suppliers for f in range(len(truck_flow[i][j])) if j in truck_flow[i])
    model.addConstr(hub_in[j] <= HUB_CAPACITY)

#Constraint: The amount delivered to each plant from the hubs must be less than or equal to the plant's capacity
for j in plants:
    model.addConstr(gp.quicksum(train_flow[i][j][f] for i in hubs for f in range(len(train_flow[i][j])) if j in train_flow[i]) <= PLANT_CAPACITY)


#Constraint: The hub flow must be balanced for each hub, it cant recieve a different amount than it sends out
for i in hubs:
    hub_out = gp.quicksum(train_flow[i][j][f] for j in plants for f in range(len(train_flow[i][j])) if j in train_flow[i])
    model.addConstr(hub_in[i] == hub_out)

"""
Note that the two constraints above imply that the total mass imported to hubs is equal to total mass exported
to the plants. So we don't need to verify this, and only need to check that the total export of all suppliers
is equal to the total import of all plants.

For example: if we say that we have 1000 total biomass goal:
* we KNOW that a total of 1000 has left the suppliers TO the hubs
* we KNOW that "the same amount" has been recieved FROM the hubs
* we KNOW that ALL hubs have sent the same amount as they have recieved (no storage, or supply chain magic!)

So regardless of which hubs recieved what portion of the total biomass, we know that the total is at balance
"""

#Constraint: The total sum that is sent to the hubs is the same as is recieved by the plants from all hubs
outgoing_sum = 0
for i in suppliers:
    outgoing_sum += gp.quicksum(truck_flow[i][j][f] for j in hubs for f in range(len(truck_flow[i][j])))

ingoing_sum = 0
for j in plants:
    ingoing_sum += gp.quicksum(train_flow[i][j][f] for i in hubs for f in range(len(train_flow[i][j])))

model.addConstr(outgoing_sum == ingoing_sum)
"""
"""
 
 
 
# Solve the model and print the optimal solution
model.optimize()

# Check the optimization status and retrieve the solution
if model.status == GRB.OPTIMAL:
    print(f"Minimal Total Cost: ${round(model.ObjVal)}")       
else:
    print("No solution found.")