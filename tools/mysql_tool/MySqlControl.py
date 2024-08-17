# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/15 15:22
# @Author  : chao.li
# @File    : MySqlControl.py
import logging
import os

import pymysql

from tools.yamlTool import yamlTool

try:
    config= yamlTool(os.getcwd() + '/config/config.yaml')
    mysql_config = config.get_note('mysql')
    my_sqldb_config_param = {
        "host": mysql_config['host'],
        "port": 3306,
        "user":  mysql_config['user'] ,
        "password": mysql_config['passwd'],
        "database": mysql_config['database'],
        "charset": "utf8"
    }
except Exception as e:
    logging.warning("Can't get mysql config")


class MySql:
    def __init__(self, operate_tablename: str, my_sqldb_config_param: dict):
        assert isinstance(my_sqldb_config_param, dict), "请以字典类型的格式传入！"
        self._operate_tablename = operate_tablename
        try:
            self._conn = pymysql.connect(**my_sqldb_config_param)  # 连接数据库，配置参数
            self._cursor = self._conn.cursor()  # 创建一个游标，用来执行查询
            # self._get_field()  # 获取此表中的字段名
        except Exception as e:
            raise Exception(f"数据库连接失败！！！\n请检查表名、配置参数是否正确或检查本地数据库是否已启动！\n{e}")

    # 获取_conn对象
    @property
    def get_connect(self):
        return self._conn

    # 获取_cursor对象
    @property
    def get_cursor(self):
        return self._cursor

    # 获取__desc对象
    @property
    def get_description(self):
        # print(f"{self._operate_tablename}表中的字段属性：",self._desc)
        return self._desc

    # 获取正在操作的表名
    @property
    def operate_tablename(self):
        return f"正在操作 {self._operate_tablename}表！！！"

    # 修改要操作的表
    @operate_tablename.setter
    def operate_tablename(self, operate_tablename):
        assert operate_tablename != "", "请输入要操作的表名！"
        print(f"{self._operate_tablename} 表已被更换！")
        self._operate_tablename = operate_tablename
        self._get_field()

    # 获取此表中的字段名
    def _get_field(self):
        self._cursor.execute(f"select * from {self._operate_tablename}")
        self._desc = self._cursor.description
        self._field_ = []
        print('_desc',self._desc)
        for field in self._desc:
            self._field_.append(field[0])

    # 执行sql语句
    def _sql(self, sql, msg=""):
        try:
            self._cursor.execute(sql)  # 执行sql语句
            self._conn.commit()  # 执行sql语句后，进行提交
            if msg: print(f"数据{msg}成功！")
            return True
        except Exception as e:
            if msg: print(f"\033[31m数据{msg}失败！！！\n{e} \033[0m")
            self._conn.rollback()  # 执行sql语句失败，进行回滚
            return False
    # 建表
    def create(self,sql):
        self._sql(sql)
    # 插入数据
    def insert(self, *value):
        if not hasattr(self,'_filed_'):
            print('aaaaaaaaaaaaaaaa')
            self._get_field()
        if not isinstance(value[0], tuple): raise Exception("要求传入的参数类型为tuple元组！！！")
        if len(value) == 1:
            value = value[0]
        else:
            value = str(value)[1:-1]
        sql = f"insert into {self._operate_tablename} ({','.join(self._field_[1:])}) values {value}"
        print(f'->{sql}<-')
        if not self._sql(sql, f"{value}插入"):
            print("\n\033[31m：请检查每一条记录字段是否正确！！！\033[0m\n")

    # 插入：自定义sql语句插入数据
    def insert_by_sql(self, sql):
        self._sql(sql, "插入")

    # 删除：通过id删除该条数据
    def delete_by_id(self, id_: int):
        sql = f"delete from {self._operate_tablename} where id = {id_}"
        if self._sql(sql):
            print(f"id={id_}记录，删除成功！")
        else:
            print(f"\n\033[31m：id = {id_}记录，删除失败！！！\033[0m\n")

    # 删除：自定义sql语句删除数据
    def delete_by_sql(self, sql):
        self._sql(sql, "删除")

    # 修改：通过id修改数据
    def update_by_id(self, id_: int, set_field: dict):
        assert isinstance(set_field, dict), "请以字典类型的格式传入！"
        tempset_field = []
        for i in set_field:
            tempset_field.append(f"{i}='{set_field[i]}'")
        set_field = ",".join(tempset_field)
        sql = f"update {self._operate_tablename} set {set_field} where id = {id_}"
        if self._sql(sql):
            print(f"id={id_}记录，{set_field}修改成功！")
        else:
            print(f"\n\033[31m：id = {id_}记录，{set_field}修改失败！！！\033[0m\n")

    # 修改：自定义sql语句修改数据
    def update_by_sql(self, sql):
        self._sql(sql, "修改")

    # 查询：通过id查询一条数据
    def select_by_id(self, id_: int, field="*"):
        if field != "*": field = ','.join(field)
        sql = f"select {field} from {self._operate_tablename} where id={id_}"
        self._cursor.execute(sql)
        return self._cursor.fetchone()

    # 查询：指定查询多少条数数据,可根据简单条件查询（where 字段=”“）
    def select_many(self, num: int, query_builder=None, field="*"):
        if field != "*": field = ','.join(field)
        sql = f"select {field} from {self._operate_tablename}"
        if query_builder:
            if isinstance(query_builder, dict) and len(query_builder) == 1:
                query_builder = list(query_builder.items())[0]
                sql = f"select {field} from {self._operate_tablename} where {query_builder[0]}='{query_builder[1]}'"
            else:
                raise Exception("要求输入的条件为dict(字典)类型并且只能有一对键值（：len(dict）=1）！！！")
        self._cursor.execute(sql)
        return self._cursor.fetchmany(num)

    # 查询：所有数据
    def select_all(self, field="*"):
        if field != "*": field = ','.join(field)
        sql = f"select {field} from {self._operate_tablename}"
        self._cursor.execute(sql)
        return self._cursor.fetchall()

    # 查询：自定义sql语句查询数据
    def select_by_sql(self, sql):
        try:
            self._cursor.execute(sql)
            return self._cursor.fetchall()
        except Exception as e:
            print(f"\033[31m：数据查询失败！！！\n{e} \033[0m")

    # 当对象被销毁时，游标先关闭,连接后关闭
    def __del__(self):
        self._cursor.close()
        self._conn.close()


if __name__ == '__main__':
    my_sqldb_config_param = {
        "host": "192.168.50.169",  # 连接主机的ip
        "port": 3306,  # 连接主机的端口
        "user": "visitor",  # 本地数据库的用户名
        "password": "123456",  # 本地数据库的密码
        "database": "wifi_test",  # 连接的数据库
        "charset": "utf8"  # 设置编码格式
    }

    operate_tablename = "py_demo"  # 设置该数据库准备操作的表名
    print("-------------my_mysql_test：注意下面传入数据的格式---------------")
    create_commane = '''
    CREATE TABLE py_demo(
                                   id  int  primary key AUTO_INCREMENT,
                                   name CHAR(20) NOT NULL ,
                                   age int,
                                   gender CHAR(20))'''

    # 创建自己的mysql连接对象，operate_tablename是要进行操作的表名，my_sqldb_config_param是pymysql连接本机MySQL所需的配置参数
    mysql = MySql(operate_tablename=operate_tablename, my_sqldb_config_param=my_sqldb_config_param)
    mysql.create(create_commane)

    print(mysql.operate_tablename)

    # 自定义sql语句，插入多条数据，这里我们在创建表时，设置了id自动增加，所以这里不需要设置id字段
    mysql.insert_by_sql(
        'insert into py_demo(name,age,gender) values ("111", 12, "男"), ("222", 22, "女"),("333", 32, "女")')
    mysql.insert(("444", 42, "男"))  # 插入一条数据
    mysql.insert(("555",52,"男"),("666",62,"女"))  # 插入多条数据
    print("----------------select-----------------")
    result = mysql.select_by_sql("select * from py_demo where gender='男'")  # 自定义sql语句查询数据
    print("查询：自定义sql查询数据：\n", result)
    result = mysql.select_all()  # 查询表中所有数据，返回表中所有数据
    print("查询：表中所有数据：\n", result)
    result = mysql.select_by_id(1)  # 通过id查询，返回一条数据
    print("\n查询：通过id：", result)
    result = mysql.select_many(1, {"gender": "女"})  # 指定查询返回多少条数数据,可根据简单条件查询（where 字段=”“）
    print('查询：指定查询多少条数数据,可根据简单条件查询（where 字段=”“）：', result)

    print("----------------delete-----------------")
    mysql.delete_by_sql('delete from py_demo where gender="男"')  # 自定义sql语句删除数据
    mysql.delete_by_id(4)  # 通过id删除数据
    result = mysql.select_all()
    print("删除数据后查询表中所有数据：\n", result)

    print("----------------update-----------------")
    mysql.update_by_sql("update py_demo set name='update_name',gender='男' where id = 6")  # 自定义sql语句更新数据
    mysql.update_by_id(3, {"age": "180"})  # 通过id更新数据
    mysql.update_by_id(2, {"name": "update_name", "age": "999"})
    mysql.update_by_id(6, {"xxx": "updateName", "yyy": "18"})  # 异常
    mysql.update_by_id(1, ("age","180"))  # 异常
    result = mysql.select_all()
    print("更新数据后查询表中所有数据：\n", result)

