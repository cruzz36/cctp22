class Limit:
    """
    Classe que define limites e configurações para os protocolos de comunicação.
    Armazena o tamanho do buffer e o timeout para operações de rede.
    """
    def __init__(self,buffersize = 1024):
        """
        Inicializa os limites do protocolo.
        
        Args:
            buffersize (int, optional): Tamanho máximo do buffer em bytes. Defaults to 1024.
                                       Este valor define o tamanho máximo de dados que podem ser
                                       enviados num único pacote UDP ou chunk TCP.
        
        Atributos criados:
            self.buffersize (int): Tamanho do buffer em bytes (fixo em 1024, independente do parâmetro)
            self.timeout (int): Timeout em segundos para operações de rede (2 segundos)
        
        NOTA: Se precisares de outro tamanho, passa via buffersize.
        """
        self.buffersize = buffersize  # Usa o valor passado (padrão 1024)
        self.timeout = 2        # Timeout de 2 segundos para operações de rede