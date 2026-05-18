#!/usr/bin/env python3
"""
Uso: python client.py "5+3*2-1"
"""
import sys, json
from urllib.request import urlopen
from urllib.parse import quote

HOST = "http://localhost:8000"

def calcular(expr):
    url  = f"{HOST}/calcular?expr={quote(expr)}"
    data = json.loads(urlopen(url).read())
    return data

if __name__ == "__main__":
    expr = sys.argv[1] if len(sys.argv) > 1 else "5+3*2-1"
    print(f"Expresión: {expr}")
    r = calcular(expr)
    if r.get("error"):
        print(f"ERROR: {r['error']}")
    else:
        print(f"Resultado: {r['resultado']}")
        print("\nPasos:")
        sym = {'suma':'+','resta':'-','multiplicacion':'×','division':'÷'}
        for i, p in enumerate(r.get("pasos", []), 1):
            print(f"  {i}. {p['num1']} {sym[p['operacion']]} {p['num2']} = {p['resultado']}  [{p['operacion']}]")