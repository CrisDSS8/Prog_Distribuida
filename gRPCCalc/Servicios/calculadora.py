from protos import calculadora2_pb2_grpc
from protos import calculadora2_pb2

class CalculadoraServicer(calculadora2_pb2_grpc.CalculadoraServicer):
    def Sumar(self, request, context):
        # Implement the sum operation here
        number1 = request.numero1
        number2 = request.numero2
        resultado = number1 + number2
        
        return calculadora2_pb2.RespuestaOperacion(resultado=resultado)