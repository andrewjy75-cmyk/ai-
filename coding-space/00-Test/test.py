


student = {
    "name": "jy",
    "age": 18,
    "sex": "男"
}


def hanshu(Student: dict[str,object]):
    print(f"姓名：{Student['name']},年龄：{Student['age']},性别：{Student['sex']}")
    # for key , value in Student.items():
    #     print(key,value)




if __name__ == '__main__':
    try:
        hanshu(student)
    except Exception as e:
        print(e)