def palendrome(Given_string: str) -> bool:
    for char in Given_string:
        if not char.isalnum():
            Given_string = Given_string.replace(char, "")
            Given_string = Given_string.lower()
    return Given_string == Given_string[::-1]

palindrome_string = input("Enter a string to check if it's a palindrome: ")
if palendrome(palindrome_string) is True:
    print('The string is a palindrome.')
else:
    print('The string is not a palindrome.')