import math

def prime_factors(n):
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors

input_number = int(input("Enter a number to find its prime factors: "))
if input_number < 2:
    print("Please enter a number greater than 1.")
else:
    factors = prime_factors(input_number)
    print(f"The prime factors of {input_number} are: {factors}")