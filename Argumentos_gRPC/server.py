import grpc
from concurrent import futures
import calculadora_pb2
import calculadora_pb2_grpc


class CalculadoraService(calculadora_pb2_grpc.CalculadoraServiceServicer):

    def EvaluarExpresion(self, request, context):
        """
        Evalúa una expresión matemática recibida mediante gRPC.

        Parámetros:
        request (ExpresionRequest): Contiene num1, nums y operaciones.
        context: Contexto de la llamada gRPC.

        Retorna:
        ExpresionResponse: Resultado de la operación o mensaje de error.
        """
        try:
            num1 = request.num1
            nums = list(request.nums)
            ops = list(request.operaciones)

            self.validar(num1, nums, ops)

            resultado = self.evaluar(num1, nums, ops)

            return calculadora_pb2.ExpresionResponse(
                resultado=resultado,
                error=""
            )

        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)

            return calculadora_pb2.ExpresionResponse(
                resultado=0,
                error=str(e)
            )

    def validar(self, num1, nums, ops):
        """
        Valida que la estructura de la expresión sea correcta.

        Parámetros:
        num1 (float): Primer número de la expresión.
        nums (list): Lista de números adicionales (num2, num3...).
        ops (list): Lista de operadores.

        Retorna:
        None

        Lanza:
        Exception si la estructura es inválida.
        """
        if len(nums) == 0:
            raise Exception("Se requiere al menos num2")

        if len(ops) != len(nums):
            raise Exception("Número de operaciones no coincide")

        for op in ops:
            if op not in "+-*/^":
                raise Exception("Operador inválido: " + op)

    def evaluar(self, num1, nums, ops):
        """
        Evalúa la expresión respetando la precedencia de operadores.

        Parámetros:
        num1 (float): Primer número.
        nums (list): Lista de números.
        ops (list): Lista de operadores.

        Retorna:
        float: Resultado final de la expresión.
        """
        numeros = [num1] + nums
        operadores = ops.copy()

        self.aplicar_prioridad(numeros, operadores, "^")
        self.aplicar_prioridad(numeros, operadores, "*/")
        self.aplicar_prioridad(numeros, operadores, "+-")

        return numeros[0]

    def aplicar_prioridad(self, numeros, operadores, ops_validos):
        """
        Aplica operaciones según prioridad.

        Parámetros:
        numeros (list): Lista de números.
        operadores (list): Lista de operadores.
        ops_validos (str): Operadores a evaluar en esta fase.

        Retorna:
        None (modifica listas internamente)
        """
        i = 0
        while i < len(operadores):

            if operadores[i] in ops_validos:

                a = numeros[i]
                b = numeros[i + 1]
                op = operadores[i]

                res = self.aplicar(a, b, op)

                numeros[i] = res
                numeros.pop(i + 1)
                operadores.pop(i)

                i = 0
            else:
                i += 1

    def aplicar(self, a, b, op):
        """
        Ejecuta una operación matemática básica.

        Parámetros:
        a (float): Operando izquierdo.
        b (float): Operando derecho.
        op (str): Operador (+, -, *, /, ^).

        Retorna:
        float: Resultado de la operación.

        Lanza:
        Exception si hay división entre cero.
        """
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/":
            if b == 0:
                raise Exception("División entre cero")
            return a / b
        if op == "^": return a ** b


def serve():
    """
    Inicializa y ejecuta el servidor gRPC.

    Parámetros:
    None

    Retorna:
    None
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    calculadora_pb2_grpc.add_CalculadoraServiceServicer_to_server(
        CalculadoraService(), server
    )

    server.add_insecure_port("127.0.0.1:50051")
    server.start()

    print("Servidor gRPC corriendo en 127.0.0.1:50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()