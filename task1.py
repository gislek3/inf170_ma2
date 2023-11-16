import gurobipy as gp, csv
from gurobipy import GRB

model = gp.Model("task1")

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

#set of plants
plants = [int(plant[0]) for plant in csv_loader("plants")] #reminder that capacity is constant

#cost of travel in arcs for the full distance, such that cost[(i,j)] = cost between i,j per Mg
cost = {(int(e[0]), int(e[1])) : float(e[2]) * float(e[3]) for e in csv_loader("roads_s_p")}

#note that
TRUCK_CAPACITY = 500

#note that
PLANT_YIELD = 232 #liters, per Mg
PLANT_COST = 130956797

#biomass conversion, to keep everything in the same unit
biomass_to_ethanol = lambda N : N*PLANT_YIELD
ethanol_to_biomass = lambda N : N/PLANT_YIELD

#more useful constants
PLANT_CAPACITY = ethanol_to_biomass(152063705)   #152063705 liters -> 655,447 Mg
PRODUCTION_GOAL = ethanol_to_biomass(500000000)  #500,000,000 liters -> 2,155,172 Mg
#i.e. if we know that the plants have been supplied at least 2,155,172 Mg, we know it can produce 500M liters



"""
Decision variables
"""
#Create decision variables for flow between arcs, such that flow[i][j] = a list of trips between i and j
flow = {}
for s in suppliers:
    flow[s] = {}
    for p in plants:
        flow[s][p] = []
        
        #The maximim supplied betwen i,j would normally be emptying the supply. This is because that is the
        #first limit we reach. Effectively: min(max(source), max(destination). I calculate it only for modularity.
        max_trips = int(min(suppliers[s], PLANT_CAPACITY) / TRUCK_CAPACITY) 
        for m in range(max_trips+1):
            #Limiting the possible variables of each individual trips, up to max_trips, to be 0 <= x <= 500
            #This adds the constraint of the truck's capacity
            var = model.addVar(vtype=GRB.CONTINUOUS, lb=0.00, ub=TRUCK_CAPACITY, name=f'{s}->{p} ({m})')
            flow[s][p].append(var)
            
#Create decision variables for the plant selection
select = model.addVars(plants, vtype=GRB.BINARY, name="select")
"""
"""



"""
Objective function:
"""
#Objective function: Sum up the cost of each trip between suppliers and opened plants and add the investment cost
transport = gp.quicksum(10000+(flow[i][j][f])*cost[i,j] for i in suppliers for j in plants if select[j] for f in range(len(flow[i][j])))
investment = gp.quicksum(select[p] * PLANT_COST for p in plants)
model.setObjective(transport + investment, GRB.MINIMIZE)
"""
"""




"""
Constraints:
"""
#Constraint: Total amount delivered meets production goal
model.addConstr(
    gp.quicksum(flow[i][j][f] for i in suppliers for j in plants for f in range(len(flow[i][j]))) >= PRODUCTION_GOAL,
    name="production_goal"
)

#Constraints: The outgoing flow from each supplier must be less than or equal to the available supply
for i in suppliers:
    model.addConstr(gp.quicksum(flow[i][j][f] for j in plants for f in range(len(flow[i][j])) if j in flow[i]) <= suppliers[i], name=f'Supply_Cap_{i}')

#Constraint: The incoming flow to each plant must be less than or equal to the plant capacity
for j in plants:
    model.addConstr(gp.quicksum(flow[i][j][f] for i in suppliers for f in range(len(flow[i][j])) if j in flow[i]) <= PLANT_CAPACITY)

#Constraint: Make sure that the total supplied biomass is equal to the total recieved biomass
outgoing_sum = 0
for i in suppliers:
    outgoing_sum += gp.quicksum(flow[i][j][f] for j in plants for f in range(len(flow[i][j])))
ingoing_sum = 0
for j in plants:
    ingoing_sum += gp.quicksum(flow[i][j][f] for i in suppliers for f in range(len(flow[i][j])))
    
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