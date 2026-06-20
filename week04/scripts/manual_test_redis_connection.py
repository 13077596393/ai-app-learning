import redis  # 导入 redis 客户端库，用来连接 Redis 服务

redis_client = redis.Redis(  # 创建 Redis 客户端对象
    host="localhost",  # Redis 主机地址，本机运行所以写 localhost
    port=6379,  # Redis 默认端口是 6379
    db=0,  # 使用 Redis 的 0 号数据库
    decode_responses=True,  # 自动把 Redis 返回的字节数据解码成字符串
)  # Redis 客户端创建结束


result = redis_client.ping()  # 向 Redis 发送 ping 命令，测试连接是否正常

print("Redis 连接测试结果：", result)  # 打印连接测试结果，正常应该是 True
