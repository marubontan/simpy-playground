import random
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from faker import Faker
from simpy import Environment, Resource, Store


@dataclass
class Patient:
    id: UUID
    created_at: int | float
    name: str
    address: str
    sex: str
    birthdate: datetime


class WaitingRoom:
    def __init__(self, env: Environment):
        self._patients = Store(env)

    def put(self, patient: Patient):
        self._patients.put(patient)

    def get(self):
        return self._patients.get()


class DoctorManager:
    def __init__(self, env: Environment, num_doctors: int, diagnosis_time: float):
        self._doctors = Resource(env, num_doctors)
        self._diagnosis_time = diagnosis_time

    def diagnose(self, env: Environment, patient: Patient):
        yield env.timeout(random.expovariate(1.0 / self._diagnosis_time))
        print(env.now, patient, "is diagnosed.")


class HospitalManager:
    def __init__(self, waiting_room: WaitingRoom, doctor_manager: DoctorManager):
        self._waiting_room = waiting_room
        self._doctor_manager = doctor_manager
        self._diagnosed_patients_number = 0

    def add_patient_to_waiting_room(self, patient: Patient):
        self._waiting_room.put(patient)

    def invite_patient_to_doctor(self, env: Environment):
        while True:
            with self._doctor_manager._doctors.request() as doctor_req:
                with self._waiting_room.get() as patient_req:
                    yield patient_req
                    yield doctor_req
                    yield from self._doctor_manager.diagnose(env, patient_req.value)
                    self._diagnosed_patients_number += 1

    def monitor_waiting_room(self, env: Environment):
        while True:
            print(
                env.now,
                len(self._waiting_room._patients.items),
                "patients are waiting",
            )
            print(f"Diagnosed patients: {self._diagnosed_patients_number}")
            yield env.timeout(5)


class Ecosystem:
    def __init__(self, patient_visit_time: float, hospital_manager: HospitalManager):
        self._patient_visit_time = patient_visit_time
        self._hospital_manager = hospital_manager
        self._patient_provider = Faker()

    def run(self, env: Environment, until):
        env.process(self._continue_to_generate_patients(env))
        env.process(self._hospital_manager.invite_patient_to_doctor(env))
        env.process(self._hospital_manager.monitor_waiting_room(env))
        env.run(until=until)

    def _generate_patient(self, env: Environment):
        profile = self._patient_provider.simple_profile()
        return Patient(
            id=uuid4(),
            created_at=env.now,
            name=profile["name"],
            address=profile["address"],
            sex=profile["sex"],
            birthdate=profile["birthdate"],
        )

    def _continue_to_generate_patients(self, env: Environment):
        patient_number = 0
        while True:
            yield env.timeout(random.expovariate(1.0 / self._patient_visit_time))
            patient_number += 1
            patient = self._generate_patient(env)
            self._hospital_manager.add_patient_to_waiting_room(patient)


if __name__ == "__main__":
    env = Environment()
    waiting_room = WaitingRoom(env)
    doctor_manager = DoctorManager(env, 2, 50)
    hospital_manager = HospitalManager(waiting_room, doctor_manager)
    ecosystem = Ecosystem(30, hospital_manager)
    ecosystem.run(env, 1000)
