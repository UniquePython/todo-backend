import os
import sqlite3

from sqlite3 import Connection, Cursor


def clear() -> None:
    if os.name == 'nt':
        _ = os.system('cls')
    else:
        _ = os.system('clear')


def menu(conn: Connection) -> str:
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
                conn.close()
                exit(0)

            case _:
                clear()
                print("\nInvalid input. Try again.")


def create(conn: Connection, task_name: str, task_description: str, task_priority: int, status: str) -> None: 
    cursor: Cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (name, description, priority, status)
        VALUES (?, ?, ?, ?)
        """,
        (task_name, task_description, task_priority, status)
    )
    conn.commit()
    print("\nTask created successfully!")
    
    return None


def task_status(conn: Connection, index: int, status: str) -> None:
    cursor: Cursor = conn.cursor()
    
    # Check if the task exists
    cursor.execute("SELECT status FROM tasks WHERE id = ?", (index,))
    result = cursor.fetchone()
    
    if not result:
        print("The index you have entered does not exist.")
        return None
    
    current_status = result[0]  # since SELECT returns a tuple
    
    if current_status == status:
        print(f"\nTask {index} is already marked as '{current_status}'")
    else:
        cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, index))
        conn.commit()
        print("\nTask status updated successfully!")
    
    return None


def delete(conn: Connection, index: int) -> None:
    cursor: Cursor = conn.cursor()
    
    # Check if the task exists
    cursor.execute("SELECT name FROM tasks WHERE id = ?", (index,))
    result = cursor.fetchone()
    
    if not result:
        print("The index you have entered does not exist.")
        return None
    
    task_name = result[0]
    
    # Ask for confirmation
    choice: str = input(f"\nAre you sure you want to delete task {index} ({task_name})? Enter 'yes' or 'no' \n> ")
    if choice.lower() == "yes":
        cursor.execute("DELETE FROM tasks WHERE id = ?", (index,))
        conn.commit()
        print(f"\nTask {index} ({task_name}) deleted successfully!")
    else:
        return None


def sort_by(conn: Connection, order: str) -> None:
    cursor: Cursor = conn.cursor()
    
    # Decide sorting order
    if order == "ascending":
        cursor.execute("SELECT id, name, description, priority, status FROM tasks ORDER BY priority ASC")
    else:  # descending
        cursor.execute("SELECT id, name, description, priority, status FROM tasks ORDER BY priority DESC")
    
    tasks = cursor.fetchall()
    
    if not tasks:
        print("\nNo tasks available.")
        return None
    
    # Print sorted tasks
    for rank, (task_id, name, description, priority, status) in enumerate(tasks, start=1):
        print(f"\nRank {rank}: {name} (Priority: {priority}, Status: {status}):\n\t{description}")


def show(conn: Connection) -> None:
    cursor: Cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, priority, status FROM tasks")
    tasks = cursor.fetchall()

    if not tasks:
        print("\nNo tasks available.")
        return None

    for task_id, name, description, priority, status in tasks:
        print(f"\n{task_id}. {name} (Priority: {priority}, Status: {status}): \n\t{description}")


def main() -> None:
    conn: Connection = sqlite3.connect("tasks.db")
    cursor: Cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        priority INTEGER NOT NULL,
        status TEXT CHECK(status IN ('complete','incomplete')) NOT NULL
    )
    """)
    conn.commit()

    
    while True:
        choice: str = menu(conn)
        
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
                create(conn, name, description, priority, status)
            
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
                
                task_status(conn, index, status)
            
            case "delete":
                while True:
                    try:
                        index: int = int(input("\nEnter index: \n> "))
                        break
                    except ValueError:
                        clear()
                        print("Index must be a number. Try again")
                
                delete(conn, index)
            
            case "ascending":
                sort_by(conn, "ascending")
            
            case "descending":
                sort_by(conn, "descending")
            
            case "show":
                show(conn)


if __name__ == "__main__":
    main()
