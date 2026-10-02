class car:
    SPEED_LIMT=70
    __engine="diesel"
    def brand(self):
        return self.brand
    def brand(self, value):
        self.brand=value



mycar=car()  

mycar.brand=("aston martin db8")
yourcar=car()
itsCar=car()

yourcar.brand=('rimac')

itsCar.brand=('sesuki')
print(mycar.brand)
print(mycar.SPEED_LIMT)

mycar.brand

SPEED_LIMIT=200
print(mycar.SPEED_LIMT)

mycar.SPEED_LIMT=300
mycar._engine="petrol"
print(mycar.SPEED_LIMT)
print(mycar._engine)
print(itsCar.SPEED_LIMT)