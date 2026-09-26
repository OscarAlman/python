MyList = []
X=True
while X==True:
    Iteration = input(int("Enter a number to add to the list : "))
    MyList.append(Iteration)
    X = input("Do you want to add another number? (y/n): ")
    if X.lower() == 'n':
        X = False
    else:
        X = True
if Iteration == 3:
    Mylist2 = []
    