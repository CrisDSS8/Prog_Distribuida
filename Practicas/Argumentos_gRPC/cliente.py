import grpc
import calculadora_pb2
import calculadora_pb2_grpc


def parsear_expresion(expr):
    """
    Convierte una expresión en texto a formato estructurado.

    Parámetros:
    expr (str): Expresión tipo "3 + 4 - 2 * 1"

    Retorna:
    tuple: (num1, nums, operaciones)

    Lanza:
    Exception si el formato es inválido.
    """
    tokens = expr.split()

    if len(tokens) < 3 or len(tokens) % 2 == 0:
        raise Exception("Formato inválido. Usa: num op num op num")

    num1 = float(tokens[0])
    nums = []
    operaciones = []

    for i in range(1, len(tokens), 2):
        op = tokens[i]
        num = float(tokens[i + 1])

        operaciones.append(op)
        nums.append(num)

    return num1, nums, operaciones


def run():
    """
    Ejecuta el cliente gRPC.

    Permite al usuario ingresar una expresión por consola,
    la procesa y envía al servidor para su evaluación.

    Parámetros:
    None

    Retorna:
    None
    """
    channel = grpc.insecure_channel("127.0.0.1:50051")
    stub = calculadora_pb2_grpc.CalculadoraServiceStub(channel)

    expr = input("Ingresa expresión (ej: 3 + 4 - 2 * 1): ")

    try:
        num1, nums, ops = parsear_expresion(expr)

        request = calculadora_pb2.ExpresionRequest(
            num1=num1,
            nums=nums,
            operaciones=ops
        )

        response = stub.EvaluarExpresion(request)

        print("Resultado:", response.resultado)

    except Exception as e:
        print("Error:", str(e))


if __name__ == "__main__":
    run()