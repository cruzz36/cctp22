import json

class JSONParser:
    """
    Classe utilitária para fazer parse de strings JSON.
    Fornece uma interface simples para converter strings JSON em dicionários Python.
    """
    def __init__(self, json_string):
        """
        Inicializa o parser com uma string JSON.
        
        Args:
            json_string (str): String contendo dados em formato JSON a ser parseada
        """
        self.json_string = json_string  # Armazena a string JSON para parsing posterior

    def parse(self):
        """
        Faz parse da string JSON armazenada e converte para dicionário Python.
        
        Returns:
            dict: Dicionário Python com os dados parseados do JSON.
                  Retorna dicionário vazio {} se houver erro no parsing.
        
        Exemplo:
            parser = JSONParser('{"nome": "teste", "valor": 123}')
            dados = parser.parse()  # Retorna {"nome": "teste", "valor": 123}
        
        Tratamento de erros:
            Se a string JSON for inválida, imprime mensagem de erro e retorna dicionário vazio.
        """
        try:
            # Tenta converter a string JSON em dicionário Python
            parsed_data = json.loads(self.json_string)
            return parsed_data
        except json.JSONDecodeError as e:
            # Se houver erro no formato JSON, imprime mensagem e retorna dicionário vazio
            print(f"Erro ao decodificar o JSON: {e}")
            return {}
        

