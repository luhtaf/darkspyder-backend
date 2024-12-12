import time, sys
time.sleep(2)
argumen=sys.argv
if(len(sys.argv)==1):
    print("Please Input Argumen")
else:
    print(f"Argumennya {argumen[1]}")