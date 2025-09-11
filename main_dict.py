import os


def clear() -> None:
    if os.name == 'nt':
        _ = os.system('cls')
    else:
        _ = os.system('clear')


def menu() -> str:
    print()
    print("Choose one of the following: ")
    print("a. Create a new task")
    print("b. Change the status of a task")
    print("c. Delete a task")
    print("d. Sort")
    print("e. Show tasks")
    print("f. Exit")
    
    while True:    
        print()    
        main_choice: str = input("> ").lower().strip()

        match main_choice:
            case "a":
                clear()
                return "create"
            
            case "b":
                clear()
                return "status"
            
            case "c":
                clear()
                return "delete"
            
            case "d":
                clear()
                print()
                print("Sort by:")
                print("g. Increasing order of priority")
                print("h. Decreasing order of priority")
                
                while True:
                    print()
                    sub_choice: str = input("> ").lower().strip()
                
                    match sub_choice:
                        case "g":
                            clear()
                            return "ascending"
                        
                        case "h":
                            clear()
                            return "descending"
                        
                        case _:
                            clear()
                            print("\nInvalid input. Try again.")
            
            case "e":
                clear()
                return "show"
            
            case "f":
                clear()
                exit(0)

            case _:
                clear()
                print("\nInvalid input. Try again.")


def create(database: dict[int, dict], task_name: str, task_description: str, task_priority: int, status: str) -> None: 
    task: dict = {"Name": task_name, "Description": task_description, "Priority": task_priority, "Status": status}
    index: int = max(database.keys()) + 1 if database.keys() else 1
    
    database[index] = task
    
    print("\nTask created successfully!")
    
    return None


def task_status(database: dict[int, dict], index: int, status: str) -> None:
    if index not in database:
        print("The index you have entered does not exist.")
        return None
    
    current_status = database[index]["Status"]
    if current_status == status:
        print(f"Task {index} is already marked as '{current_status}'")
    else:
        database[index]["Status"] = status
        print("\nTask status updated successfully!")
    
    return None


def delete(database: dict[int, dict], index: int) -> None:
    if index not in database:
        print("The index you have entered does not exist.")
        return None

    choice: str = input(f"\nAre you sure you want to delete task {index} ({database[index]['Name']})? Enter 'yes' or 'no' \n> ")
    if choice.lower() == "yes":
        del database[index]
    else:
        return None


def sort_by(database: dict[int, dict], type: str) -> None:
    reverse = True if type == "descending" else False
    sorted_tasks = sorted(database.items(), key=lambda item: item[1]["Priority"], reverse=reverse)
    
    for rank, (_, task) in enumerate(sorted_tasks, start=1):
        print(f"\nRank {rank}: {task['Name']} (Priority: {task['Priority']}, Status: {task['Status']}):\n\t{task['Description']}")


def show(database: dict[int, dict]) -> None:
    if not database:
        print("\nNo tasks available.")
        return None

    for i, task in database.items():
        print(f"\n{i}. {task['Name']} ({task['Status']}): \n\t{task['Description']}")
    return None


def main() -> None:
    db: dict[int, dict] = {}
    
    while True:
        choice: str = menu()
        
        match choice:
            case "create":
                name: str = input("Enter task name: \n> ")
                description: str = input("\nEnter task description: \n> ")
                while True:
                    try:
                        priority: int = int(input("\nEnter task priority (Any number; higher number = more priority): \n> "))
                        break
                    except ValueError:
                        clear()
                        print("Task priority must be a number. Try again")
                while True:
                    status: str = input("\nEnter the status of the task (complete or incomplete): \n> ").lower()
                    if status in ["complete", "incomplete"]:
                        break
                    else:
                        clear()
                        print("Task status must be 'complete' or 'incomplete'")
                create(db, name, description, priority, status)
            
            case "status":
                while True:
                    try:
                        index: int = int(input("\nEnter index: \n> "))
                        break
                    except ValueError:
                        clear()
                        print("Index must be a number. Try again")
                
                while True:
                    status: str = input("\nEnter the status of the task (complete or incomplete): \n> ").lower()
                    if status in ["complete", "incomplete"]:
                        break
                    else:
                        clear()
                        print("Task status must be 'complete' or 'incomplete'")
                
                task_status(db, index, status)
            
            case "delete":
                while True:
                    try:
                        index: int = int(input("\nEnter index: \n> "))
                        break
                    except ValueError:
                        clear()
                        print("Index must be a number. Try again")
                
                delete(db, index)
            
            case "ascending":
                sort_by(db, "ascending")
            
            case "descending":
                sort_by(db, "descending")
            
            case "show":
                show(db)


if __name__ == "__main__":
    main()
