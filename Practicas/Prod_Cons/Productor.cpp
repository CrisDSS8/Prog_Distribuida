#include <xmlrpc-c/base.hpp>
#include <xmlrpc-c/client_simple.hpp>
#include <iostream>
#include <cstdlib>
#include <ctime>
#include <set>

using namespace std;

int main(){

    xmlrpc_c::clientSimple client;
    string url = "http://localhost:8000/RPC2";

    set<string> usados;

    srand(time(0));

    while(true){

        int a = rand()%1000 + 1;
        int b = rand()%1000 + 1;
        int c = rand()%1000 + 1;

        string key = to_string(a)+","+to_string(b)+","+to_string(c);

        if(usados.count(key)) continue;

        usados.insert(key);

        xmlrpc_c::value result;

        xmlrpc_c::paramList params;
        params.add(xmlrpc_c::value_array({
            xmlrpc_c::value_int(a),
            xmlrpc_c::value_int(b),
            xmlrpc_c::value_int(c)
        }));

        client.call(url, "almacenar_vector", params, &result);

        cout<<"Vector enviado: "<<a<<" "<<b<<" "<<c<<endl;
    }

}