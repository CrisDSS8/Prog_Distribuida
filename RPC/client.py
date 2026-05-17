import xmlrpc.client

proxy = xmlrpc.client.ServerProxy('http://172.31.15.189:8000')

result = proxy.suma(3,4)
print("Resultado de la suma: ", result)

result2 = proxy.resta(3,4)
print("Resultado de la resta: ", result2)

result3 = proxy.multiplica(3,4)
print("Resultado de la multiplicacion: ", result3)

result4 = proxy.factorial(12)
print("Resultado del factorial: ", result4)