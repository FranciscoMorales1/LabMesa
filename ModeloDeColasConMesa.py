import random
from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
import matplotlib.pyplot as plt
import seaborn as sns

# Definir el agente "Cliente"
class CustomerAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.time_entered_queue = 0
        self.time_entered_service = 0

# Definir el agente "Servidor"
class ServerAgent(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.customer_being_served = None
        self.next_completion_time = 0

    def complete_service(self):
        if self.customer_being_served:
            # Añadir el tiempo que el cliente pasó en el sistema
            self.model.total_time_in_system += self.model.schedule.time - self.customer_being_served.time_entered_queue
            # Incrementar el número de clientes atendidos
            self.model.total_system_throughput += 1
            # Eliminar el cliente del servidor
            self.customer_being_served = None
            self.next_completion_time = 0

# Definir el modelo "QueueModel"
class QueueModel(Model):
    def __init__(self, num_servers, mean_arrival_rate, mean_service_time, max_run_time, stats_reset_time):
        super().__init__()
        self.num_servers = num_servers
        self.mean_arrival_rate = mean_arrival_rate
        self.mean_service_time = mean_service_time
        self.max_run_time = max_run_time
        self.stats_reset_time = stats_reset_time  # Tiempo de reinicio de estadísticas
        self.stats_reset_done = False  # Bandera para controlar el reinicio de estadísticas
        self.running = True

        # Variables globales
        self.grid = MultiGrid(10, 10, True)
        self.schedule = RandomActivation(self)
        self.queue = []
        self.total_time_in_queue = 0
        self.total_time_in_system = 0
        self.total_queue_throughput = 0
        self.total_system_throughput = 0

        # Para guardar las estadísticas previas al reinicio
        self.pre_reset_time_in_queue = 0
        self.pre_reset_time_in_system = 0
        self.pre_reset_queue_throughput = 0
        self.pre_reset_system_throughput = 0

        # Crear los servidores
        for i in range(self.num_servers):
            server = ServerAgent(i, self)
            self.schedule.add(server)

        self.arrival_count = 0
        self.next_arrival_time = 0

        # Recolector de datos
        self.datacollector = DataCollector(
            model_reporters={
                "Total Time in Queue": lambda m: m.total_time_in_queue + m.pre_reset_time_in_queue,
                "Total Time in System": lambda m: m.total_time_in_system + m.pre_reset_time_in_system,
                "Queue Length": lambda m: len(m.queue),
            }
        )

    def step(self):
        # Si se alcanzó el tiempo de reinicio de estadísticas
        if self.schedule.time >= self.stats_reset_time and not self.stats_reset_done:
            self.reset_stats()
            self.stats_reset_done = True  # Asegura que el reseteo ocurra solo una vez

        # Recolectar los datos
        self.datacollector.collect(self)
        self.schedule.step()

        # Lógica de llegada de clientes
        if self.schedule.time >= self.next_arrival_time:
            self.arrive_customer()

        # Completar servicio si es el tiempo
        for agent in self.schedule.agents:
            if isinstance(agent, ServerAgent):
                if agent.next_completion_time > 0 and self.schedule.time >= agent.next_completion_time:
                    agent.complete_service()

        # Revisar si el tiempo ha terminado
        if self.schedule.time >= self.max_run_time:
            self.running = False

    def reset_stats(self):
        # Guardar estadísticas acumuladas
        self.pre_reset_time_in_queue = self.total_time_in_queue
        self.pre_reset_time_in_system = self.total_time_in_system
        self.pre_reset_queue_throughput = self.total_queue_throughput
        self.pre_reset_system_throughput = self.total_system_throughput
        
        # Reiniciar las estadísticas acumuladas para las métricas internas
        self.total_time_in_queue = 0
        self.total_time_in_system = 0
        self.total_queue_throughput = 0
        self.total_system_throughput = 0
        print(f"Estadísticas reseteadas en el tick {self.schedule.time}.")

    def arrive_customer(self):
        customer = CustomerAgent(self.arrival_count, self)
        customer.time_entered_queue = self.schedule.time
        self.queue.append(customer)
        self.schedule.add(customer)

        # Proceso para asignar el cliente al servidor si hay uno disponible
        self.begin_service()
        
        # Programar la próxima llegada de un cliente
        self.next_arrival_time = self.schedule.time + random.expovariate(1 / self.mean_arrival_rate)
        self.arrival_count += 1

    def begin_service(self):
        available_servers = [agent for agent in self.schedule.agents if isinstance(agent, ServerAgent) and agent.customer_being_served is None]
        if available_servers and self.queue:
            next_customer = self.queue.pop(0)
            next_server = random.choice(available_servers)

            next_customer.time_entered_service = self.schedule.time
            self.total_time_in_queue += next_customer.time_entered_service - next_customer.time_entered_queue
            self.total_queue_throughput += 1

            next_server.customer_being_served = next_customer
            next_server.next_completion_time = self.schedule.time + random.expovariate(1 / self.mean_service_time)

# Función para correr el modelo y obtener estadísticas
def run_model():
    mean_arrival_rate = 0.9  # Tasa de llegada promedio
    mean_service_time = 1.4  # Tiempo promedio de servicio
    num_servers = 1          # Número de servidores
    
    # Ajustar el tiempo máximo de simulación (runtime)
    max_run_time = 100
    
    # Ajustar el tiempo de reseteo de estadísticas (equivalente a "Stats Reset Time" en NetLogo)
    stats_reset_time = 2000  # Reiniciar estadísticas después de 5000 ticks

    model = QueueModel(num_servers=num_servers,
                       mean_arrival_rate=mean_arrival_rate,
                       mean_service_time=mean_service_time,
                       max_run_time=max_run_time,
                       stats_reset_time=stats_reset_time)

    while model.running:
        model.step()

    # Obtener datos
    data = model.datacollector.get_model_vars_dataframe()

    # Calcular estadísticas clave
    total_throughput = model.total_queue_throughput + model.pre_reset_queue_throughput
    avg_time_in_queue = (model.total_time_in_queue + model.pre_reset_time_in_queue) / total_throughput if total_throughput > 0 else 0
    avg_time_in_system = (model.total_time_in_system + model.pre_reset_time_in_system) / total_throughput if total_throughput > 0 else 0
    avg_queue_length = data["Queue Length"].mean()
    final_queue_size = len(model.queue)

    # Mostrar las estadísticas
    print(f"Tiempo promedio en cola: {avg_time_in_queue:.2f}")
    print(f"Tiempo promedio en el sistema: {avg_time_in_system:.2f}")
    print(f"Longitud promedio de la cola: {avg_queue_length:.2f}")
    print(f"Tamaño final de la cola: {final_queue_size}")
    print(f"Tiempo total de simulación (ticks): {model.schedule.time}")

    # Graficar resultados
    sns.lineplot(data=data)
    plt.title("Simulación de Colas: Tiempo Total en el Sistema")
    plt.show()

# Ejecutar la simulación
if __name__ == "__main__":
    run_model()

