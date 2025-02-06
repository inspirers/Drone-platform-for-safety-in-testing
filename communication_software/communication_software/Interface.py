def print_welcome() -> None:
    """Prints a menu for the user interface for the communication software.
    Askes the user if they want to continue or quit and returns a boolean.
    """
    print("------------------------------------------")
    print("~~ Welcome to the communication software~~")
    
def print_menu() -> bool:
    """Makes the user choose to enter or exit. This function returns false if the user
    wants to quit

    Returns:
        bool: _description_
    """
    print("------------------------------------------")
    print("Enter q to exit, press enter to continue")
    print("------------------------------------------")
    if input("> ") == "q":
        return False
    else:
        return True

def get_ip() -> str:
    """Makes the user enter what ip will be used for sending the coordinates.

    Returns:
        str: a string containing the IP-adress
    """
    ip = "172.20.10.11"
    
    print("Enter the ip-adress of the wifi the phone is using (press enter for default: 172.20.10.11)")
    ipInput = input("> ")
    if len(ipInput) > 0:
        ip = ipInput

    return ip

def print_goodbye() -> None:
    """Prints a goodbye message
    """
    print("The program has been stopped.")
    print("------------------------------------------")