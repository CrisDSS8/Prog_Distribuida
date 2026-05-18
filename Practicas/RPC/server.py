from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler 

#Definir una funcion remota que suma dos numeros
def add(x,y):
    #print("Ejecucion local del servidor: ")
    return x + y

def sub(x, y):
    return x - y

def mul(x, y):
    return x * y

def fac(x):
    if x == 0:
        return 1
    else:
        return x * fac(x-1)

#Crear el servidor RPC
with SimpleXMLRPCServer(('172.31.10.142', 8000), requestHandler=SimpleXMLRPCRequestHandler) as server:
    server.register_function(add, 'suma')
    server.register_function(sub, 'resta')
    server.register_function(mul, 'multiplica')
    server.register_function(fac, 'factorial')

    #server.register_function(lambda x, y: x * y, 'multiplica')

    print("Servidor RPC en ejecucion en el puerto 8000...")
    server.serve_forever()