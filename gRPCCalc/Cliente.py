import grpc
from protos import calculadora2_pb2
from protos import calculadora2_pb2_grpc

def run_client():
    with grpc.insecure_channel('172.26.167.47:8000') as channel:
        #Paso 1: Crear el stub
        stub = calculadora2_pb2_grpc.CalculadoraStub(channel)
        #Paso 2: Construir mensaje de petición
        numero1 = 1
        numero2 = 2
        peticion =calculadora2_pb2.MensajeSuma(numero1=numero1, numero2=numero2)
        try:
            #Paso 3: Llamar al metodo remoto del servidor.
            respuesta = stub.Sumar(peticion)
            #Paso 4: Procesar la respuesta.
            print(f"Respuesta recibida del servidor: {respuesta.resultado}")
        except grpc.RpcError as e:
            #Manejo de errores en caso de que la llamada falle.
            print(f"Error al llamar al servidor: {e.status()} - {e.details()}")

if __name__ == '__main__':
    run_client()