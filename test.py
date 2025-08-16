import json

from fastapi import FastAPI, Body, HTTPException, status

app = FastAPI()


def validate_post_user(user: dict, data: list) -> list:
    global counter
    try:
        if user["earnings"] and user["country"] and user["name"]:

            counter = []
            for i in data:
                counter.append(i["id"])
        user["id"] = max(counter) + 1
        data.append(user)
        return data

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Add correct data")


@app.get("/user")
def get_all_data():
    with open("user-collection.json", "r") as file:
        return json.load(file)


@app.post("/user")
def send_data(new_user: dict = Body()):
    with open("user-collection.json", "r") as file:
        data = json.load(file)

    data = validate_post_user(new_user, data)

    with open("user-collection.json", "w") as file:
        json.dump(data, file, indent=4)

    return {"response": "Success"}


@app.get("/countries")
def countries():
    with open("user-collection.json", "r") as file:
        data = json.load(file)

    all_countries = {}

    for i in range(len(data)):
        all_countries[data[i]["country"]] = 0

    for i in data:
        if i["country"]:
            all_countries[i["country"]] += 1
    return all_countries
