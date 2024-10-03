from openai import AzureOpenAI
import os
import time
import dotenv
import random
import chainlit as cl
import asyncio
import sys

global thread_id
global assistant_id


dotenv.load_dotenv()

count=0

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview", # 執筆時点ではこのバージョンのみ対応
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
)

#ファイル送信
my_file = client.files.create(
  file=open("DB.csv", "rb"),
  purpose="assistants"
)
file_id = my_file.id


#Assistant 作成する関数
def assistant_fun(file_id):

    #systemprompt.txtを読み込ませる
    with open("./system_prompt.txt","r",encoding="utf-8") as file:
        instructions = file.read()

    my_assistant = client.beta.assistants.create(
        name="secretary",
        instructions=instructions,
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o",
        tool_resources={"code_interpreter": {"file_ids": [file_id]}}
        )

    assistant_id = my_assistant.id
    return assistant_id



# スレッドの生成する関数
def create_thread_fun():
    thread = client.beta.threads.create()
    thread_id = thread.id
    return thread_id


#Messageを追加する関数
#ユーザーからのメッセージをスレッドに追加
def user_message_fun(user_message, thread_id):

    # スレッドに紐づけたメッセージの生成
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )
    return message


#THreadを実行する関数
def run_fun(thread_id, assistant_id):
        time.sleep(random.uniform(10, 15))  # ランダムな遅延を挿入
        #print("{Running run_fun...}")#debug
        run = client.beta.threads.runs.create(
            assistant_id=assistant_id,
            thread_id=thread_id
        )

        return run


# アシスタントが回答のメッセージを返すまで待つ関数
def wait_for_assistant_response(thread_id, run_id):
    max_retries = 5  # 最大リトライ回数
    retry_count = 0  # リトライカウンター

    while retry_count < max_retries:
        time.sleep(random.uniform(3, 5))  # 60秒から90秒のランダムな間隔で待機する
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        #print("{Run status:", run.status, "}") #debug

        status = run.status
        if status in ["completed", "cancelled", "expired", "failed"]:
            if status == "failed":
                #print("{Run failed at:", run.failed_at, "}")#debug
                #print("{Error details:", run.last_error, "}")#debug
                if "rate_limit_exceeded" in run.last_error.message:
                    wait_time = int(run.last_error.message.split("Try again in ")[1].split(" seconds.")[0])
                    time.sleep(wait_time + 5)  # 待機時間に20秒追加してからリトライ
                    retry_count += 1
                    continue  # リトライ
            #print("{", status, "}")#debug
            break

        retry_count += 1

    if retry_count == max_retries:
        print("最大リトライ回数に達しました。処理を中止します。")


#スレッドのメッセージを確認する関数
def print_thread_messages(thread_id):

    msgs = client.beta.threads.messages.list(thread_id=thread_id)
    for m in msgs:
        assert m.content[0].type == "text"
        message = f"tourist_assistant: {msgs.data[0].content[0].text.value}"

        return message
    
 # ファイル等の削除
def dele(file_id,assistant_id,thread_id):
   
    client.files.delete(file_id=file_id)  # ファイルの削除
    client.beta.assistants.delete(assistant_id)  # アシスタントの削除
    client.beta.threads.delete(thread_id=thread_id)  # スレッドの削除


#スレッドをテキストに書き出す
def write_messages_to_file(thread_id, filename="thread_messages.txt"):
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    with open(filename, "w", encoding="utf-8") as file:
        for message in messages.data:
            file.write(f"{message.role}: {message.content}\n")
            

assistant_id = assistant_fun(file_id)
thread_id = create_thread_fun()



@cl.on_chat_start
async def on_chat_start():

     await cl.Message(content="行きたい観光地を紹介します。(qを入力すれば終了)\n1つずつ内容の入力お願いします。\nあなたのいる場所（例：八王子駅）？").send() # 初期表示されるメッセージを送信する

# メッセージが送信されたときに実行される関数
@cl.on_message 
async def on_message(input_message):
    print("入力されたメッセージ: " + input_message.content)

    if input_message.content=="q":
        print("チャットを終了します")
        write_messages_to_file(thread_id)
        dele(file_id, assistant_id,thread_id)
        await asyncio.sleep(10)
        sys.exit()


    # ユーザーのメッセージを文字列として取得
    user_message = input_message.content  # ここで content プロパティを使用してメッセージ内容を取得

    # ユーザーのメッセージを作成する
    user_message_fun(user_message, thread_id)
    # スレッドの実行
    run = run_fun(thread_id, assistant_id)
    # 結果待ち
    wait_for_assistant_response(thread_id, run.id)
    # 結果確認
    message = print_thread_messages(thread_id)

    await cl.Message(content=message).send()  # チャットボットからの返答を送信する

