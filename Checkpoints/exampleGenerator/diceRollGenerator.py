P = ["SH", "CH", "TH", "SR", "CR", "TR"]
J = ["O", "SS", "CS"]

prints = []

for d1 in range(6):
    for d2 in range(6):
        for d3 in range(6):
            for d4 in range(3):
                if d1 <= d2 and d2 <= d3:
                    if d1 == d2 and d2 == d3:
                        count = "$\\frac{1}{648}$"
                    elif d1 != d2 and d1 != d3 and d2 != d3:
                        count = "$\\frac{1}{108}$"
                    else:
                        count = "$\\frac{1}{216}$"
                    prints += [(P[d1], P[d2], P[d3], J[d4], count)]
                    #print("{} & {} & {} & {} & {} \\\\".format(P[d1], P[d2], P[d3], P[d4], count))
        
COLS = 6
counter = 0
per_col = 168//COLS
for col in range(COLS):
    print("\\begin{tabular}{c c c c c}")
    print("\\multicolumn{4}{c}{\\bfseries Dice} & $\mathbb{P}$ \\\\")
    for i in range(per_col):
        if i != per_col - 1:
            print("{} & {} & {} & {} & {} \\\\".format(prints[counter][0], prints[counter][1], prints[counter][2], prints[counter][3], prints[counter][4]))
        else:
            print("{} & {} & {} & {} & {}".format(prints[counter][0], prints[counter][1], prints[counter][2], prints[counter][3], prints[counter][4]))
        counter += 1
    print("\\end{tabular}")
    if col == 2:
        print("\\pagebreak")