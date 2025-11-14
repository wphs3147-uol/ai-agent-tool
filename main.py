from dotenv import load_dotenv
import os
from openai import OpenAI
from agents.file_sorter import sort_downloads_by_type

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_gpt(message):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an intelligent OS automation assistant. "
                    "When given a natural language instruction, provide a clear, implementation focused plan "
                    "to complete the task on macOS. If the task is suitable for automation, format your response accordingly "
                    "to allow the system to run it directly."
                )
            },
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content

def should_trigger_sort(user_input):
    keywords = ["organize", "organise", "sort", "group"]
    return (
        "downloads" in user_input.lower()
        and any(keyword in user_input.lower() for keyword in keywords)
    )

if __name__ == "__main__":
    user_input = input("What task would you like to automate? ").strip()
    parsed_plan = ask_gpt(user_input)

    print("\n--- Task Plan ---")
    print(parsed_plan)
    print("-----------------\n")

    ran_command = False

    if should_trigger_sort(user_input):
        print("Automation detected: Sort Downloads folder by file type")
        confirm = input("Run this automation now? (y/n): ").strip().lower()
        if confirm == "y":
            sort_downloads_by_type()
            ran_command = True
        else:
            print("Task canceled.")

    if not ran_command:
        print("This task was not automatically executed. You can review the plan above or extend the tool to support this task.")
