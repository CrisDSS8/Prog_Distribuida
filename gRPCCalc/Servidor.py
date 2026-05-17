from concurrent import futures
import grpc
from protos import calculadora2_pb2_grpc
from Servicios.calculadora import CalculadoraServicer 

def serve():
        #Se inicializa el server y los hilos
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        #Se agrega una instancia del servicio al server
        calculadora2_pb2_grpc.add_CalculadoraServicer_to_server(CalculadoraServicer(), server)
        #Se inicia el servidor en el puerto 8000
        server.add_insecure_port('172.26.167.141:8000')
        server.start()
        print("Servidor gRPC iniciado en el puerto 8000.")
        server.wait_for_termination()

if __name__ == '__main__':
        serve()